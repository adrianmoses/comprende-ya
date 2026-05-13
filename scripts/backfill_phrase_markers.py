"""Backfill phrase markers + segment tokens for a video processed before 018.

Runs ONLY the marker step (one Claude call) against an existing video's
segments — no Whisper, no question regen, no exercise regen. Pre-warms the
phrase_autopsy cache the same way `save_phrase_markers_task` does.

Usage:
    uv run python scripts/backfill_phrase_markers.py <video_db_id>
    uv run python scripts/backfill_phrase_markers.py --youtube-id <youtube_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from db import get_db_session  # noqa: E402
from models.database import VideoSegment  # noqa: E402
from repositories import SegmentsRepository, VideoRepository  # noqa: E402
from repositories.autopsy_repository import AutopsyRepository, normalize_phrase  # noqa: E402
from services.phrase_markers import (  # noqa: E402
    PhraseMarkersGenerationError,
    phrase_markers_service,
)
from services.segment_tokenizer import tokenize_segment  # noqa: E402
from services.spanish_nlp import get_nlp  # noqa: E402


def resolve_video_id(args: argparse.Namespace) -> int:
    if args.video_id is not None:
        return args.video_id
    if args.youtube_id is None:
        raise SystemExit("provide either --youtube-id or a positional video_db_id")
    with get_db_session() as db:
        video = VideoRepository(db).get_by_youtube_id(args.youtube_id)
        if video is None:
            raise SystemExit(f"no video with youtube_id={args.youtube_id}")
        return video.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_id", type=int, nargs="?", help="DB id of the video")
    parser.add_argument("--youtube-id", help="YouTube id of the video (alt to positional)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run Claude + tokenize, print summary, no DB writes",
    )
    args = parser.parse_args()

    video_id = resolve_video_id(args)

    print(f"📥 Cargando segmentos para video_id={video_id}…")
    with get_db_session() as db:
        segments = SegmentsRepository(db).get_by_video_id(video_id)
        if not segments:
            raise SystemExit(f"no hay segmentos para video_id={video_id}")
        # detach: we'll reopen a fresh session before persisting
        segments_data = [
            (s.id, s.segment_number, s.transcript_text, s.start_time) for s in segments
        ]
        # rebuild lightweight segment list for the prompt builder
        prompt_segments = [
            VideoSegment(
                id=sid,
                video_id=video_id,
                segment_number=n,
                transcript_text=text,
                start_time=t,
                end_time=0.0,
            )
            for sid, n, text, t in segments_data
        ]
    print(f"✅ {len(prompt_segments)} segmentos cargados")

    print("🤖 Llamando a Claude para generar marcadores… (puede tardar ~10–30 s)")
    try:
        markers = phrase_markers_service.explain_video(prompt_segments)
    except PhraseMarkersGenerationError as exc:
        raise SystemExit(f"❌ Generación de marcadores falló: {exc}")
    print(f"✅ {len(markers)} marcadores devueltos:")
    for m in markers:
        print(f"   - seg {m['segment_number']:>3}: «{m['phrase']}» — {m['register']}")

    nlp = get_nlp()
    by_segment: dict[int, list] = defaultdict(list)
    for m in markers:
        by_segment[m["segment_number"]].append(m)

    if args.dry_run:
        print("\n🔍 Dry run — tokenizando para inspección, sin escribir a la DB.")
        located = 0
        dropped = 0
        for sid, n, text, _ in segments_data:
            seg_markers = by_segment.get(n, [])
            if not seg_markers:
                continue
            span_phrases = [(i, m["tokens_in_segment"]) for i, m in enumerate(seg_markers)]
            tokens = tokenize_segment(text, span_phrases, nlp)
            spans_seen = {tok.get("span") for tok in tokens if "span" in tok}
            for i, m in enumerate(seg_markers):
                if i in spans_seen:
                    located += 1
                else:
                    dropped += 1
                    print(f"   ⚠️  seg {n}: span no localizado para «{m['phrase']}»")
        print(f"\n📊 Localizados: {located} / {located + dropped}")
        return

    print("\n💾 Tokenizando segmentos y persistiendo…")
    written = 0
    autopsy_created = 0
    with get_db_session() as db:
        autopsy_repo = AutopsyRepository(db)
        for sid, n, text, start_time in segments_data:
            seg_markers = by_segment.get(n, [])
            span_phrases = [(i, m["tokens_in_segment"]) for i, m in enumerate(seg_markers)]
            tokens = tokenize_segment(text, span_phrases, nlp)
            db_seg = db.get(VideoSegment, sid)
            if db_seg is None:
                continue
            db_seg.tokens = json.dumps(tokens, ensure_ascii=False)
            db.add(db_seg)
            written += 1

            for m in seg_markers:
                phrase_key = normalize_phrase(m["phrase"])
                if autopsy_repo.get_by_phrase(video_id, phrase_key):
                    continue
                autopsy_repo.create(
                    video_id=video_id,
                    phrase=m["phrase"],
                    start_time=start_time,
                    payload={
                        "register": m["register"],
                        "grammar": m["grammar"],
                        "natural_notes": m["natural_notes"],
                    },
                )
                autopsy_created += 1
        db.commit()

    print(f"✅ tokens escritos en {written} segmentos")
    print(f"✅ {autopsy_created} filas pre-pobladas en phrase_autopsy")
    print("\n👉 Refresca http://localhost:3000/listen/<youtube_id> para ver los spans.")


if __name__ == "__main__":
    main()
