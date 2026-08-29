# -*- coding: utf-8 -*-
"""GitHub 기여 잔디를 shell-page 테마의 SVG 로 그린다.

외부 카드 서비스(vercel 등)는 레이트리밋으로 자주 깨지므로 직접 생성한다.
데이터는 GraphQL contributionCalendar 를 그대로 쓴다.
"""
import io, json, os, sys, urllib.request

LOGIN = os.environ.get("CONTRIB_LOGIN", "ParkJaeHwan-906")
OUT   = os.environ.get("CONTRIB_OUT", "contributions.svg")

QUERY = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

C = dict(bg="#0d1117", head="#161b22", border="#21262d",
         fg="#c9d1d9", dim="#6e7681", green="#3fb950")
# 0 → 4 단계. 마지막이 shell-page 강조색과 같다.
SCALE = ["#161b22", "#0e4429", "#1a7f37", "#2ea043", "#3fb950"]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "contrib-svg"})
    body = json.loads(urllib.request.urlopen(req).read().decode())
    if "errors" in body:
        raise SystemExit("GraphQL error: %s" % body["errors"])
    user = body["data"]["user"]
    if not user:
        raise SystemExit("no such user: %s" % LOGIN)
    return user["contributionsCollection"]["contributionCalendar"]


def bucket(n, tiers):
    if n <= 0:
        return 0
    for i, t in enumerate(tiers):
        if n <= t:
            return i + 1
    return 4


def build(cal):
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    nz = sorted(d["contributionCount"] for d in days if d["contributionCount"] > 0)
    # 사분위로 색 단계를 나눈다 (하루 최대치가 커도 잔디가 뭉개지지 않게)
    tiers = [nz[int(len(nz) * q)] for q in (0.25, 0.5, 0.75)] if nz else [1, 2, 3]

    CELL, GAP, PAD = 10, 3, 20
    step = CELL + GAP
    LEFT, TOPLBL, HEAD = 30, 16, 34
    grid_x = PAD + LEFT
    grid_y = HEAD + PAD + TOPLBL
    W = grid_x + len(weeks) * step - GAP + PAD
    H = grid_y + 7 * step - GAP + 34 + PAD

    p = []
    p.append('<rect x="0.5" y="0.5" width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>'
             % (W - 1, H - 1, C["bg"], C["border"]))
    p.append('<path d="M0.5 10.5a10 10 0 0 1 10-10h%d a10 10 0 0 1 10 10v%d h-%d z" fill="%s" stroke="%s"/>'
             % (W - 21, HEAD - 11, W - 1, C["head"], C["border"]))
    p.append('<text x="20" y="22.4" fill="%s" font-size="11.5">$ contributions --year</text>' % C["dim"])
    p.append('<text x="%d" y="22.4" fill="%s" font-size="11.5" text-anchor="end">%s contributions</text>'
             % (W - 20, C["green"], format(cal["totalContributions"], ",")))

    # 월 라벨 — 그 달이 처음 등장하는 주에만
    seen = set()
    for wi, w in enumerate(weeks):
        first = w["contributionDays"][0]["date"]
        y, m = int(first[:4]), int(first[5:7])
        if (y, m) in seen:
            continue
        seen.add((y, m))
        if wi > len(weeks) - 3:
            continue
        p.append('<text x="%d" y="%d" fill="%s" font-size="10">%s</text>'
                 % (grid_x + wi * step, grid_y - 6, C["dim"], MONTHS[m - 1]))

    for wd, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        p.append('<text x="%d" y="%d" fill="%s" font-size="10" text-anchor="end">%s</text>'
                 % (grid_x - 6, grid_y + wd * step + CELL - 1, C["dim"], lab))

    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            b = bucket(d["contributionCount"], tiers)
            p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"><title>%s: %d</title></rect>'
                     % (grid_x + wi * step, grid_y + d["weekday"] * step,
                        CELL, CELL, SCALE[b], d["date"], d["contributionCount"]))

    ly = grid_y + 7 * step + 16
    p.append('<text x="%d" y="%d" fill="%s" font-size="10">Less</text>' % (grid_x, ly + 9, C["dim"]))
    for i, col in enumerate(SCALE):
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"/>'
                 % (grid_x + 32 + i * step, ly, CELL, CELL, col))
    p.append('<text x="%d" y="%d" fill="%s" font-size="10">More</text>'
             % (grid_x + 32 + len(SCALE) * step + 4, ly + 9, C["dim"]))

    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'role="img" aria-label="GitHub contributions">\n'
            '  <title>contributions --year</title>\n'
            '  <g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,\'DejaVu Sans Mono\',monospace">\n'
            '%s\n  </g>\n</svg>\n'
            % (W, H, W, H, '\n'.join('    ' + x for x in p)))


if __name__ == "__main__":
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        sys.exit("GH_TOKEN / GITHUB_TOKEN 이 필요합니다.")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(build(fetch(tok)))
    print("wrote", OUT)
