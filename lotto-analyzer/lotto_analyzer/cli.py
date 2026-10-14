"""명령줄 사용법:  python -m lotto_analyzer <명령> [옵션]

  update               새 회차 당첨번호 받아오기 (처음엔 1회부터 전부)
  stats                번호별 출현 횟수, hot/cold, 함께 나온 번호 등 보기
  check 1 2 3 4 5 6    내 조합이 역대에 몇 등까지 맞았는지 확인
  pick                 조건에 맞는 번호 조합 만들기
  report               Markdown 리포트 파일 만들기
  import-csv 파일      CSV(회차,날짜,번호1~6,보너스)로 데이터 넣기 (API가 막혔을 때)
"""

import argparse
import csv
import sys
from pathlib import Path

from . import fetch, stats
from .generator import STRATEGIES, Filters, Generator
from .report import build_report


def _fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def _load(args):
    draws = fetch.load_draws(args.data)
    if not draws:
        print("저장된 데이터가 없습니다. 먼저 `python -m lotto_analyzer update`를 실행하세요.")
        sys.exit(1)
    return draws


def _bar(value, max_value, width=30):
    return "█" * round(width * value / max_value) if max_value else ""


def cmd_update(args):
    before = len(fetch.load_draws(args.data))
    print(f"현재 저장된 회차: {before}개. 새 회차를 확인합니다...")
    added = fetch.update(args.data, delay=args.delay)
    if added:
        last = added[-1]
        print(f"{len(added)}개 회차 추가. 최신 {last['round']}회 ({last['date']}): "
              f"{_fmt(last['numbers'])} + 보너스 {last['bonus']:02d}")
    else:
        print("새로 추가된 회차가 없습니다 (이미 최신이거나 아직 추첨 결과가 올라오지 않음).")


def cmd_stats(args):
    draws = _load(args)
    target = draws[-args.recent:] if args.recent else draws
    title = f"최근 {len(target)}회" if args.recent else f"전체 {len(target)}회"
    freq = stats.number_frequency(target, include_bonus=args.bonus)
    gap = stats.last_seen_gap(draws)
    top = max(freq.values())

    print(f"\n[{title} 번호별 출현 횟수{' (보너스 포함)' if args.bonus else ''}]  "
          f"({draws[0]['round']}~{draws[-1]['round']}회 데이터)")
    order = sorted(stats.ALL_NUMBERS, key=lambda n: (-freq[n], n)) if args.sort else stats.ALL_NUMBERS
    for n in order:
        print(f"  {n:2d} | {freq[n]:4d} {_bar(freq[n], top):<30} 미출현 {gap[n]}회")

    hot, cold, _ = stats.hot_cold(draws, recent=args.recent, size=args.top)
    print(f"\n많이 나온 {args.top}개: {_fmt(hot)}")
    print(f"적게 나온 {args.top}개: {_fmt(cold)}")
    overdue = sorted(stats.ALL_NUMBERS, key=lambda n: -gap[n])[:args.top]
    print("오래 안 나온 번호: " + ", ".join(f"{n}({gap[n]}회)" for n in overdue))

    print(f"\n[자주 함께 나온 번호 쌍 TOP {args.top}]")
    for p, c in stats.pair_frequency(target, top=args.top):
        print(f"  {_fmt(p)} : {c}회")

    print("\n[이전 당첨번호 중복 검사]")
    for line in stats.describe_repeat_check(stats.repeat_check(draws)):
        print("  " + line)

    lo, hi = stats.sum_range(draws)
    odd = stats.shape_distribution(draws, stats.odd_count)
    print(f"\n번호 합계 가운데 80% 범위: {lo} ~ {hi}")
    print("홀수 개수 분포: " + ", ".join(f"{k}개 {odd[k] / len(draws):.1%}" for k in range(7)))


def cmd_check(args):
    draws = _load(args)
    combo = sorted(set(args.numbers))
    if len(combo) != 6 or not all(1 <= n <= 45 for n in combo):
        print("1~45 사이 서로 다른 번호 6개를 넣어 주세요.")
        return 1
    res = stats.find_combo(draws, combo)
    print(f"\n조합 {_fmt(combo)} 를 {len(draws)}회와 비교했습니다.")
    labels = [(6, "1등(6개)"), ("5+bonus", "2등(5개+보너스)"), (5, "3등(5개)"),
              (4, "4등(4개)"), (3, "5등(3개)")]
    for key, label in labels:
        rounds = res[key]
        shown = ", ".join(map(str, rounds[-10:])) + (" ..." if len(rounds) > 10 else "")
        print(f"  {label}: {len(rounds)}번" + (f"  ({shown})" if rounds else ""))
    if not res[6]:
        print("  -> 역대 1등 번호와 똑같은 적은 없는 조합입니다.")


def cmd_pick(args):
    draws = _load(args)
    common = dict(past_policy=args.past, repeat_threshold=args.threshold,
                  max_overlap_with_past=args.max_overlap)
    if args.no_filter:
        filters = Filters(**common, odd_range=(0, 6), low_range=(0, 6), sum_coverage=0,
                          max_run=6, min_decade_spread=1)
    else:
        filters = Filters(**common, sum_coverage=args.sum_coverage, max_run=args.max_run)
    gen = Generator(draws, recent=args.recent, pool_size=args.pool, filters=filters, seed=args.seed)

    print("\n[1단계] 이전 당첨번호 중복 검사")
    for line in stats.describe_repeat_check(gen.repeat):
        print("  " + line)
    if args.past != "auto":
        print(f"  (--past {args.past} 지정: 이전 1등 조합을 {'제외' if gen.exclude_past else '제외하지 않음'})")

    try:
        tickets = gen.generate(count=args.count, strategy=args.strategy, n_hot=args.hot,
                               n_cold=args.cold, include=args.include, exclude=args.exclude)
    except (ValueError, RuntimeError) as e:
        print(f"오류: {e}")
        return 1

    basis = f"최근 {args.recent}회" if args.recent else f"전체 {len(draws)}회"
    print(f"\n[2단계] {args.strategy} 전략으로 번호 조합 ({basis} 기준 / {draws[-1]['round']}회까지 반영)")
    if args.strategy == "mix":
        print(f"  많이 나온 번호 {args.hot}개 + 덜 나온·오래 안 나온 번호 {args.cold}개 + 나머지 무작위")
    print(f"  hot 후보: {_fmt(sorted(gen.hot_pool))}")
    print(f"  cold 후보: {_fmt(sorted(gen.cold_pool))}")
    if not args.no_filter:
        print(f"  모양 필터: 합계 {gen.sum_lo}~{gen.sum_hi}, 홀짝·고저 쏠림 제외, "
              f"{args.max_run + 1}연속 이상 제외 (--no-filter로 끄기)")
    print()
    for i, t in enumerate(tickets, 1):
        tags = []
        if t.hot:
            tags.append("hot " + ",".join(map(str, t.hot)))
        if t.cold:
            tags.append("cold " + ",".join(map(str, t.cold)))
        print(f"  {chr(64 + i) if i <= 26 else i}) {_fmt(t.numbers)}   "
              f"합 {t.total:3d} | 홀{stats.odd_count(t.numbers)}:짝{6 - stats.odd_count(t.numbers)} | "
              + " / ".join(tags))
    print("\n※ 모든 조합의 1등 확률은 똑같이 8,145,060분의 1입니다. 통계는 번호를 고르는 기준일 뿐입니다.")


def cmd_report(args):
    draws = fetch.load_draws(args.data)
    text = build_report(draws, recent=args.recent, picks=args.count, seed=args.seed)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"리포트를 {args.out}에 저장했습니다.")


def cmd_import_csv(args):
    draws = {d["round"]: d for d in fetch.load_draws(args.data)}
    with open(args.file, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().isdigit():
                continue  # 머리글 줄 건너뛰기
            r = int(row[0])
            nums = sorted(int(x) for x in row[2:8])
            draws[r] = {"round": r, "date": row[1].strip(), "numbers": nums,
                        "bonus": int(row[8]), "first_prize_amount": 0, "first_prize_winners": 0}
    fetch.save_draws(list(draws.values()), args.data)
    print(f"총 {len(draws)}개 회차를 저장했습니다.")


def build_parser():
    p = argparse.ArgumentParser(prog="python -m lotto_analyzer", description="로또 6/45 통계·번호 생성기",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--data", default=fetch.DEFAULT_DATA_PATH, help="데이터 파일 경로")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("update", help="새 회차 받아오기")
    s.add_argument("--delay", type=float, default=0.2, help="요청 사이 대기 시간(초)")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("stats", help="통계 보기")
    s.add_argument("--recent", type=int, help="최근 N회만 보기")
    s.add_argument("--top", type=int, default=10, help="TOP 몇 개까지 보여줄지")
    s.add_argument("--sort", action="store_true", help="출현 횟수 순으로 정렬")
    s.add_argument("--bonus", action="store_true", help="보너스 번호도 횟수에 포함")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("check", help="내 조합 역대 당첨 확인")
    s.add_argument("numbers", type=int, nargs=6)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("pick", help="번호 조합 만들기")
    s.add_argument("-n", "--count", type=int, default=5, help="몇 게임 만들지 (기본 5)")
    s.add_argument("-s", "--strategy", choices=STRATEGIES, default="mix")
    s.add_argument("--hot", type=int, default=3, help="mix: 많이 나온 번호 몇 개 (기본 3)")
    s.add_argument("--cold", type=int, default=2, help="mix: 덜 나온 번호 몇 개 (기본 2)")
    s.add_argument("--recent", type=int, help="최근 N회 기준으로 hot/cold 판단")
    s.add_argument("--pool", type=int, default=15, help="hot/cold 후보 개수 (기본 15)")
    s.add_argument("-i", "--include", type=int, nargs="*", default=[], help="꼭 넣을 번호")
    s.add_argument("-x", "--exclude", type=int, nargs="*", default=[], help="뺄 번호")
    s.add_argument("--past", choices=("auto", "exclude", "allow"), default="auto",
                   help="이전 1등 조합 처리: auto=중복 검사 결과로 결정(기본), exclude=항상 제외, allow=제외 안 함")
    s.add_argument("--threshold", type=float, default=0.01,
                   help="auto일 때 다음 회차 중복 확률이 이 값보다 낮으면 제외 (기본 0.01 = 1%%)")
    s.add_argument("--max-overlap", type=int, default=6,
                   help="이전 1등과 최대 몇 개까지 겹쳐도 되는지 (기본 6 = 검사 안 함, 예: 4)")
    s.add_argument("--max-run", type=int, default=2, help="연속번호 최대 길이 (기본 2)")
    s.add_argument("--sum-coverage", type=float, default=0.8, help="합계 허용 범위 비율 (기본 0.8, 0=끔)")
    s.add_argument("--no-filter", action="store_true", help="모양 필터 모두 끄기")
    s.add_argument("--seed", type=int, help="같은 결과를 다시 보고 싶을 때 쓰는 시드")
    s.set_defaults(func=cmd_pick)

    s = sub.add_parser("report", help="Markdown 리포트 만들기")
    s.add_argument("--out", default="REPORT.md")
    s.add_argument("--recent", type=int, default=50)
    s.add_argument("-n", "--count", type=int, default=5)
    s.add_argument("--seed", type=int)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("import-csv", help="CSV로 데이터 넣기")
    s.add_argument("file")
    s.set_defaults(func=cmd_import_csv)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except fetch.FetchError as e:
        print(f"데이터 조회 실패: {e}")
        return 2
