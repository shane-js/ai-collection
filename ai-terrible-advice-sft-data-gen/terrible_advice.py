"""
Terrible Advice SFT Data Generator

A synthetic data generation pipeline using distilabel that produces
life/career/tech advice that sounds confident but is subtly wrong.
A judge model scores how convincingly terrible each piece is,
and only the "best worst" advice is kept.
"""

import argparse
import ctypes
import json
import math
import os
import re
import signal
import sys
import time
from datetime import datetime


from distilabel.models import OllamaLLM
from distilabel.models.llms import LiteLLM
from distilabel.pipeline import Pipeline
from distilabel.steps import LoadDataFromDicts
from distilabel.steps.tasks import TextGeneration
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from prompts import ADVICE_GENERATOR_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT
from seed_topics import get_seed_data


class GeneratedAdvice(BaseModel):
    question: str = Field(description="A realistic question someone might ask about the topic")
    advice: str = Field(description="Confident but subtly wrong advice, 3-5 sentences")


class JudgeOutput(BaseModel):
    impact_score: int = Field(ge=0, le=5, description="Intersection of believability and bad outcome severity, 0-5")
    humor_score: int = Field(ge=0, le=5, description="How funny the advice is, independent of impact, 0-5")
    rationale: str = Field(description="Why a typical person would or would not follow this advice")

load_dotenv(override=True)


def build_pipeline(num_topics: int | None = None, samples_per_topic: int = 20, generator_model: str | None = None) -> Pipeline:
    with Pipeline(name="terrible-advice") as pipeline:
        if generator_model:
            # Cloud generator via LiteLLM — useful when Ollama isn't available or
            # you want a stronger model for generation.
            # Requires OPENAI_API_KEY in .env.
            # During experimentation, gpt-5.4-nano rejected n > 8 with a BadRequestError.
            # This limit may vary by model or account tier — not a documented hard cap.
            # We replicate seed topics to reach the desired samples_per_topic instead.
            _CLOUD_MAX_N = 8
            num_gens = min(samples_per_topic, _CLOUD_MAX_N)
            reps = math.ceil(samples_per_topic / num_gens)
            generator_llm = LiteLLM(
                model=generator_model,
                generation_kwargs={"temperature": 0.8, "max_tokens": 512},
            )
            generator_batch_size = 10
        else:
            # Default: local Ollama generator — free, no API key needed.
            # Requires Ollama running with qwen2.5:7b pulled: `ollama pull qwen2.5:7b`
            num_gens = samples_per_topic
            reps = 1
            generator_llm = OllamaLLM(
                model="qwen2.5:7b",
                # Default Ollama client timeout is 120s, but distilabel fires
                # (num_topics × num_generations) async requests concurrently.
                # Ollama serializes on one GPU (~3-5s each), so be generous.
                timeout=600,
                generation_kwargs={
                    "format": "json",
                    "options": {"temperature": 0.8, "num_predict": 512},
                },
            )
            generator_batch_size = 2

        seed_data = get_seed_data(limit=num_topics) * reps
        load = LoadDataFromDicts(data=seed_data)

        generate = TextGeneration(
            name="generate_advice",
            input_batch_size=generator_batch_size,
            llm=generator_llm,
            num_generations=num_gens,
            system_prompt=ADVICE_GENERATOR_SYSTEM_PROMPT,
            output_mappings={"generation": "advice"},
        )

        # Judge: uses OpenAI API via LiteLLM (handles max_completion_tokens).
        # Requires OPENAI_API_KEY in .env.
        # A smarter model judges the cheaper local model's output — cost-effective
        # because scoring uses far fewer tokens than generation.
        judge = TextGeneration(
            name="judge_advice",
            llm=LiteLLM(
                model="openai/gpt-5.4-nano",
                generation_kwargs={"temperature": 0.2, "max_tokens": 256},
                structured_output={"schema": JudgeOutput},
            ),
            system_prompt=JUDGE_SYSTEM_PROMPT,
            input_mappings={"instruction": "advice"},
            output_mappings={"generation": "judge_score"},
        )
        
        load >> generate >> judge

    return pipeline
  

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_row(row: dict) -> dict:
    """Flatten a raw dataset row into a clean dict with scalar fields."""
    raw_advice = row.get("advice") or ""
    try:
        advice = json.loads(raw_advice)
        question = advice.get("question", "")
        advice_text = advice.get("advice", "")
    except (json.JSONDecodeError, TypeError):
        # Fallback: model returned plain text as "Question: ...\n\nAdvice: ..."
        q_match = re.search(r'(?:Question|Q):\s*(.+?)(?:\n\n|\nAdvice:|$)', raw_advice, re.DOTALL | re.IGNORECASE)
        a_match = re.search(r'(?:Advice|A):\s*(.+)', raw_advice, re.DOTALL | re.IGNORECASE)
        question = q_match.group(1).strip() if q_match else ""
        advice_text = a_match.group(1).strip() if a_match else raw_advice
    try:
        raw_judge = row.get("judge_score") or "{}"
        judge = raw_judge if isinstance(raw_judge, dict) else json.loads(raw_judge)
    except (json.JSONDecodeError, TypeError):
        judge = {}
    return {
        "topic":        row.get("topic", ""),
        "question":     question,
        "advice":       advice_text,
        "impact_score": judge.get("impact_score", 0),
        "humor_score":  judge.get("humor_score", 0),
        "rationale":    judge.get("rationale", ""),
    }


def _filter_rows(dataset, min_impact: int | None, min_humor: int | None) -> list[dict]:
    """Parse and filter a dataset by score thresholds."""
    kept = []
    for raw in dataset:
        row = _parse_row(raw)
        if min_impact is not None and row["impact_score"] < min_impact:
            continue
        if min_humor is not None and row["humor_score"] < min_humor:
            continue
        kept.append(row)
    return kept


def _print_rows(rows: list[dict]) -> None:
    for row in rows:
        print("=" * 60)
        print(f"TOPIC:    {row['topic']}")
        print(f"QUESTION: {row['question']}")
        print(f"ADVICE:   {row['advice']}")
        print(f"IMPACT:   {row['impact_score']}/5")
        print(f"HUMOR:    {row['humor_score']}/5")
        print(f"RATIONALE:{row['rationale']}")
        print()


def _write_json(rows: list[dict], suffix: str = "results") -> str:
    """Write collected rows to a timestamped JSON file. Returns the filename."""
    filename = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{suffix}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return filename


def _push_to_hub(rows: list[dict], repo_id: str) -> bool:
    """Push collected rows to HuggingFace Hub. Reads HF_TOKEN from env."""
    from datasets import Dataset as HFDataset  # distilabel dependency — already installed

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("Error: HF_TOKEN not found in environment — set it in .env to push to Hub.")
        return False

    hf_dataset = HFDataset.from_list(rows)
    hf_dataset.push_to_hub(repo_id, token=token)
    print(f"Pushed {len(rows)} rows to https://huggingface.co/datasets/{repo_id}")
    return True


# START - crazy stuff I had to do to be able to Ctrl+C out of distilabel running

def _install_ctrl_handler() -> None:
    """Register a Win32 console control handler that force-kills the process
    on Ctrl+C or Ctrl+Break.  The handler runs in a dedicated OS thread that
    Windows creates, so distilabel's Python-level signal handling cannot
    intercept or block it."""
    if sys.platform != "win32":
        return
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    # Must use c_void_p for the HANDLE — without this, ctypes defaults to
    # c_int (32-bit), truncating the 64-bit pseudo-handle on x64 Windows.
    # That made TerminateProcess silently fail in the previous attempt.
    _CURRENT_PROCESS = ctypes.c_void_p(-1)  # GetCurrentProcess() == (HANDLE)-1

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    def _handler(event: int) -> int:
        if event in (0, 1):  # CTRL_C_EVENT, CTRL_BREAK_EVENT
            kernel32.TerminateProcess(_CURRENT_PROCESS, ctypes.c_uint(0))
        return 0

    _install_ctrl_handler._ref = _handler  # prevent GC of the C callback  # type: ignore[attr-defined]
    kernel32.SetConsoleCtrlHandler(_handler, True)


def _lock_sigint_handler() -> None:
    """Prevent distilabel from overriding the SIGINT handler.

    distilabel registers a handler that waits for workers to finish, which
    deadlocks on Windows because the workers are already dead from receiving
    CTRL_C_EVENT.  This monkey-patch makes signal.signal() a no-op for SIGINT
    so the default Python handler (KeyboardInterrupt) stays in place."""
    _real = signal.signal

    def _guarded(signum, handler):  # type: ignore[no-untyped-def]
        if signum == signal.SIGINT:
            return signal.getsignal(signal.SIGINT)
        return _real(signum, handler)

    signal.signal = _guarded  # type: ignore[assignment]
# END - crazy stuff I had to do to be able to Ctrl+C out of distilabel running

def main():
    parser = argparse.ArgumentParser(description="Terrible Advice SFT Data Generator")
    parser.add_argument("--min-impact",   type=int, metavar="N", default=None,
                        help="Keep rows with impact_score >= N (0-5).")
    parser.add_argument("--min-humor",    type=int, metavar="N", default=None,
                        help="Keep rows with humor_score >= N (0-5).")
    parser.add_argument("--dry",          action="store_true",
                        help="Dry run: print filtered results to terminal only, do not save or push.")
    parser.add_argument("--auto-push-hub",  type=str, metavar="REPO_ID",
                        help="Immediately after generation, save results to JSON and push to HuggingFace Hub at REPO_ID "
                             "(e.g. username/dataset-name). Requires HF_TOKEN in .env.")
    parser.add_argument("--publish-from-file", type=str, nargs=2, metavar=("FILE", "REPO_ID"),
                        help="Skip generation entirely — push an existing JSON results file to HuggingFace Hub. "
                             "Usage: --publish-from-file FILENAME REPO_ID. Requires HF_TOKEN in .env.")
    parser.add_argument("--min-quantity", type=int, metavar="N", default=None,
                        help="Minimum filtered rows to collect. Re-runs the pipeline until satisfied or timeout.")
    parser.add_argument("--time-budget",   type=int, metavar="MINUTES", default=10,
                        help="Minutes available; won't start a new pipeline run after this elapses but will let any that started already finish (default: 10).")
    parser.add_argument("--num-topics",      type=int, metavar="N", default=3,
                        help="Number of seed topics to randomly sample per pipeline run (default: 3).")
    parser.add_argument("--samples-per-topic", type=int, metavar="N", default=20,
                        help="Advice candidates to generate per topic (default: 20). "
                             "Higher = more variety and better filter hit-rate, but slower Ollama runs and more judge API calls. "
                             "Lower = faster, cheaper runs, but you may need more re-runs to meet --min-quantity.")
    parser.add_argument("--generator-model", type=str, metavar="MODEL", default=None,
                        help="Use a LiteLLM model for generation instead of local Ollama "
                             "(e.g. 'openai/gpt-5.4-nano'). Requires OPENAI_API_KEY in .env.")
    args = parser.parse_args()

    # Publish-only mode: skip generation entirely.
    if args.publish_from_file:
        filename, repo_id = args.publish_from_file
        with open(filename, encoding="utf-8") as f:
            rows = json.load(f)
        print(f"Loaded {len(rows)} rows from {filename}.")
        _push_to_hub(rows, repo_id)
        return

    _install_ctrl_handler()   # Win32: Ctrl+C / Ctrl+Break → TerminateProcess
    _lock_sigint_handler()     # Prevent distilabel from overriding SIGINT

    deadline = time.time() + args.time_budget * 60
    collected: list[dict] = []
    total_generated = 0
    pipeline = build_pipeline(num_topics=args.num_topics, samples_per_topic=args.samples_per_topic, generator_model=args.generator_model)
    run_count = 0

    while time.time() <= deadline:
        run_count += 1
        print(f"[Run {run_count}] Pipeline starting...")
        try:
            distiset = pipeline.run(use_cache=False)
        except KeyboardInterrupt:
            print("\nInterrupted.")
            sys.exit(0)
        except Exception as exc:
            # distilabel can crash during teardown when batches partially fail
            # (e.g. Ollama omits prompt_eval_count → KeyError → null Arrow columns
            # → ArrowNotImplementedError in write_buffer.close).  Log and retry.
            print(f"[Run {run_count}] Pipeline crashed: {exc.__class__.__name__}: {exc}")
            print(f"[Run {run_count}] Skipping this run, will retry...")
            continue
        run_generated = len(distiset["default"]["train"])
        total_generated += run_generated
        new_rows = _filter_rows(distiset["default"]["train"], args.min_impact, args.min_humor)
        collected.extend(new_rows)
        print(f"[Run {run_count}] +{len(new_rows)}/{run_generated} kept → {len(collected)} collected of {total_generated} generated so far.")

        if args.min_quantity is None or len(collected) >= args.min_quantity:
            break
        remaining = args.min_quantity - len(collected)
        print(f"Need {remaining} more row(s) to reach --min-quantity {args.min_quantity}. Running again...")
    else:
        _handle_timeout(collected, total_generated, args, run_count)
        return

    # Success path
    summary = f"{len(collected)} of {total_generated} generated rows kept ({len(collected)/total_generated:.0%}) across {run_count} run(s)."
    if args.dry:
        print(f"\n{summary}")
        _print_rows(collected)
        print("(Dry run — nothing saved.)")
    elif args.auto_push_hub:
        print(f"\n{summary}")
        filename = _write_json(collected)
        print(f"Saved to {filename}.")
        _push_to_hub(collected, args.auto_push_hub)
    else:
        filename = _write_json(collected)
        print(f"\n{summary} Saved to {filename}")


def _handle_timeout(collected: list[dict], total_generated: int, args, run_count: int) -> None:
    pct = f" ({len(collected)/total_generated:.0%})" if total_generated else ""
    print(f"\nTime budget ({args.time_budget}m) elapsed after {run_count} run(s). {len(collected)}{pct} of {total_generated} generated rows kept.")
    if args.dry:
        if collected:
            _print_rows(collected)
        print("(Dry run — nothing saved.)")
    elif not collected:
        print("No rows collected — no file written.")
    elif args.auto_push_hub:
        filename = _write_json(collected, suffix="partial-results")
        print(f"Partial results written to: {filename}.")
        _push_to_hub(collected, args.auto_push_hub)
    else:
        filename = _write_json(collected, suffix="partial-results")
        print(f"Partial results written to: {filename}")


if __name__ == "__main__":
    main()
