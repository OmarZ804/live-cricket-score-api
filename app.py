import requests
from bs4 import BeautifulSoup
import re
import html
import time
from typing import List, Optional

import re
import html
import urllib.request
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import (
    JSONResponse,
    PlainTextResponse,
    HTMLResponse,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException


NOT_FOUND = "score not found"
REQUEST_TIMEOUT = "request timeout"
INVALID_MATCH_ID = "invalid score id"


class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class Batsman(BaseModel):
    name: str = NOT_FOUND
    score: str = NOT_FOUND


class Bowler(BaseModel):
    name: str = NOT_FOUND


class ScoreResponse(BaseModel):
    status: str
    title: str
    score: str
    current_batsmen: List[Batsman]
    current_bowler: Bowler


class MatchValidator(BaseModel):
    score: str

    @field_validator("score")
    @classmethod
    def validate_match_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(INVALID_MATCH_ID)

        if not value.isdigit():
            raise ValueError("score id must contain digits only")

        if len(value) < 4:
            raise ValueError("score id must be at least 4 digits")

        if len(value) > 20:
            raise ValueError("score id too long")

        return value


app = FastAPI(
    title="Score API",
    version="0.0.1",
    description="Live Cricket Score JSON API",
    docs_url=None,
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, "
        "proxy-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000"
    )

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "object-src 'none'; "
        "frame-ancestors 'none';"
    )

    return response


class ScoreService:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/146.0.0.0 "
            "Safari/537.36"
        ),
        "Referer": "https://www.cricbuzz.com/",
        "Origin": "https://www.cricbuzz.com",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Connection": "close",
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return NOT_FOUND
        return html.escape(" ".join(text.split()))

    @classmethod
    def default_batsmen(cls) -> List[Batsman]:
        return [Batsman(), Batsman()]

    @classmethod
    def format_tree(cls, data: ScoreResponse) -> str:
        batsmen_lines = "\n".join(
            f"│   ├── {player.name} : {player.score}"
            for player in data.current_batsmen
        )

        return (
            "🏏 Live Score\n"
            "│\n"
            f"├── Match    : {data.title}\n"
            f"├── Score    : {data.score}\n"
            f"├── Bowler   : {data.current_bowler.name}\n"
            "├── Batsmen\n"
            f"{batsmen_lines}"
        )

    @classmethod
    async def fetch_score(cls, match_id: str) -> ScoreResponse:
        try:
            url = (
                "https://www.cricbuzz.com/live-cricket-scores/"
                f"{match_id}?_={time.time_ns()}"
            )

            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers=cls.HEADERS
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            title = cls.clean(
                re.sub(
                    r"^Cricket commentary\s*\|\s*",
                    "",
                    soup.title.get_text(strip=True)
                    if soup.title
                    else NOT_FOUND,
                    flags=re.IGNORECASE
                )
            )

            og_tag = soup.find("meta", property="og:title")
            og_title = og_tag.get("content", "") if og_tag else ""

            score = NOT_FOUND

            score_match = re.search(
                r"([A-Z]{2,4})\s+(\d+)/(\d+)\s*\(([\d.]+)\)",
                og_title
            )

            if score_match:
                team, runs, wickets, overs = score_match.groups()
                score = f"{team} {runs}/{wickets} ({overs})"

            batsmen = []

            batsman_match = re.search(
                r"\((.*?)\)\s*\|",
                og_title
            )

            if batsman_match:
                players = re.findall(
                    r"([A-Za-z\s.'-]+)\s+(\d+\(\d+\))",
                    batsman_match.group(1)
                )

                batsmen = [
                    Batsman(
                        name=cls.clean(name),
                        score=cls.clean(score_value)
                    )
                    for name, score_value in players[:2]
                ]

            if len(batsmen) < 2:
                batsmen = cls.default_batsmen()

            page_text = cls.clean(
                soup.get_text(" ", strip=True)
            )

            bowler_match = re.search(
                r"Bowler.*?([A-Za-z.'\- ]+?)\s+\d+\s+\d+",
                page_text,
                re.IGNORECASE
            )

            bowler_name = (
                cls.clean(bowler_match.group(1))
                if bowler_match
                else NOT_FOUND
            )

            return ScoreResponse(
                status="success",
                title=title,
                score=score,
                current_batsmen=batsmen,
                current_bowler=Bowler(name=bowler_name)
            )

        except httpx.TimeoutException:
            raise APIError(408, REQUEST_TIMEOUT)

        except httpx.HTTPStatusError:
            raise APIError(404, "score data unavailable")

        except Exception:
            raise APIError(500, "failed to process score data")

@app.get("/docs", include_in_schema=False)
async def custom_swagger_docs():
    try:
        html = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="Live Cricket Score API Docs",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
        )

        content = html.body.decode("utf-8")

        if "</head>" not in content:
            raise ValueError("Invalid Swagger HTML")

        custom_style = """
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1">
        <style>
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                overflow-x: hidden;
                -webkit-text-size-adjust: 100%;
            }

            .swagger-ui {
                width: 100%;
                overflow-x: hidden;
            }

            .swagger-ui .wrapper {
                width: 100%;
                max-width: 100% !important;
                padding: 10px !important;
                box-sizing: border-box;
            }

            .swagger-ui .opblock-summary {
                flex-wrap: wrap !important;
                gap: 6px;
            }

            .swagger-ui .opblock-summary-path {
                white-space: normal !important;
                word-break: break-word !important;
                overflow-wrap: anywhere !important;
                font-size: 14px !important;
                line-height: 1.4;
            }

            .swagger-ui pre,
            .swagger-ui code,
            .swagger-ui .microlight,
            .swagger-ui .highlight-code {
                white-space: pre-wrap !important;
                word-break: break-word !important;
                overflow-wrap: anywhere !important;
                overflow-x: auto !important;
                max-width: 100% !important;
                max-height: 220px !important;
                overflow-y: auto !important;
                box-sizing: border-box;
                font-size: 12px !important;
                line-height: 1.5 !important;
                border-radius: 8px;
            }

            .swagger-ui table {
                display: block;
                width: 100%;
                overflow-x: auto;
            }

            .swagger-ui textarea,
            .swagger-ui input,
            .swagger-ui select {
                width: 100% !important;
                box-sizing: border-box;
                font-size: 16px !important;
            }

            .swagger-ui .btn {
                min-height: 42px !important;
                white-space: normal !important;
            }

            @media (max-width: 768px) {
                .swagger-ui .wrapper {
                    padding: 8px !important;
                }

                .swagger-ui pre,
                .swagger-ui code {
                    max-height: 180px !important;
                    font-size: 11px !important;
                }
            }
        </style>
        """

        content = content.replace(
            "</head>",
            custom_style + "</head>"
        )

        response = HTMLResponse(content=content)

        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

        return response

    except Exception:
        return HTMLResponse(
            content="""
            <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Docs Error</title>
                </head>
                <body style="font-family:sans-serif;padding:20px;">
                    <h2>Unable to load Swagger docs</h2>
                </body>
            </html>
            """,
            status_code=500
        )

@app.get("/", response_model=ScoreResponse)
async def root(
    score: Optional[str] = Query(
        None,
        min_length=4,
        max_length=20
    ),
    text: bool = Query(False)
):
    if score is None:
        return ScoreResponse(
            status="success",
            title="Live Score API",
            score=NOT_FOUND,
            current_batsmen=ScoreService.default_batsmen(),
            current_bowler=Bowler()
        )

    try:
        MatchValidator(score=score)
    except Exception as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": 422,
                "message": "score id must be at least 4 digits"
            }
        )

    result = await ScoreService.fetch_score(score)

    if text:
        return PlainTextResponse(
            ScoreService.format_tree(result)
        )

    return result


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": "score id must be at least 4 digits"
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": "invalid api route"
        }
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": "internal server error"
        }
    )
    import requests
from bs4 import BeautifulSoup

@app.get("/full-scorecard/{match_id}")
def get_full_scorecard(match_id: str):
    url = f"https://www.cricbuzz.com/live-cricket-scorecard/{match_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return {"status": "error", "match_id": match_id, "scorecard": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    innings_list = []

    bat_rows = soup.find_all("div", class_=lambda c: c and "scorecard-bat-grid" in c)
    bowl_rows = soup.find_all("div", class_=lambda c: c and "scorecard-bowl-grid" in c)

    batting_data = []
    for row in bat_rows:
        name_el = row.find("span", class_="hover:underline")
        if not name_el:
            continue  # Skips header row ("Batter", "R", etc.)
        name = name_el.get_text(strip=True)
        
        dismissal_el = row.find("div", class_=lambda c: c and "text-cbTxtSec" in c)
        dismissal = dismissal_el.get_text(strip=True) if dismissal_el else "not out"
        
        cols = row.find_all("div", class_=lambda c: c and "flex justify-center" in c)
        runs = cols[0].get_text(strip=True) if len(cols) > 0 else "0"
        balls = cols[1].get_text(strip=True) if len(cols) > 1 else "0"
        fours = cols[2].get_text(strip=True) if len(cols) > 2 else "0"
        sixes = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
        
        batting_data.append({
            "name": name,
            "dismissal": dismissal,
            "runs": runs,
            "balls": balls,
            "fours": fours,
            "sixes": sixes
        })

    bowling_data = []
    for row in bowl_rows:
        name_el = row.find("span", class_="hover:underline")
        if not name_el:
            continue  # Skips header row ("Bowler", "O", etc.)
        name = name_el.get_text(strip=True)
        
        cols = row.find_all("div", class_=lambda c: c and "flex justify-center" in c)
        overs = cols[0].get_text(strip=True) if len(cols) > 0 else "0"
        maidens = cols[1].get_text(strip=True) if len(cols) > 1 else "0"
        runs = cols[2].get_text(strip=True) if len(cols) > 2 else "0"
        wickets = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
        
        bowling_data.append({
            "name": name,
            "overs": overs,
            "maidens": maidens,
            "runs": runs,
            "wickets": wickets
        })

    if batting_data or bowling_data:
        innings_list.append({"batting": batting_data, "bowling": bowling_data})

    return {"status": "success", "match_id": match_id, "scorecard": innings_list}


@app.get("/series/{series_id}")
def get_series_matches(series_id: str):
    """
    Scrapes all matches and details for a given Cricbuzz Series ID.
    Example: GET /series/13257
    """
    url = f"https://www.cricbuzz.com/cricket-series/{series_id}/matches"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            page_html = resp.read().decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from Cricbuzz: {str(e)}")

    title_match = re.search(r"<title>(.*?)</title>", page_html)
    raw_title = title_match.group(1) if title_match else f"Series {series_id}"
    series_name = html.unescape(raw_title.split(" schedule")[0].split(" | Cricbuzz")[0].strip())

    main_idx = page_html.find("<main")
    main_content = page_html[main_idx:] if main_idx != -1 else page_html

    matches = []
    seen = set()
    links = re.findall(
        r'<a[^>]*href="/live-cricket-scores/(\d+)/([^"]+)"[^>]*>(.*?)</a>',
        main_content,
        re.DOTALL,
    )

    for mid, slug, link_text in links:
        if mid in seen:
            continue
        clean_text = re.sub(r"<[^>]*>", " ", link_text)
        clean_text = html.unescape(re.sub(r"\s+", " ", clean_text)).strip()
        if not clean_text or clean_text.lower().startswith("live"):
            continue

        seen.add(mid)
        matches.append({
            "match_id": mid,
            "title": clean_text,
            "slug": slug,
        })

    return {
        "status": "success",
        "series_id": series_id,
        "series_name": series_name,
        "total_matches": len(matches),
        "matches": matches,
    }


def extract_match_squads(match_id: str):
    url = f"https://www.cricbuzz.com/cricket-match-squads/{match_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Cricbuzz returned status {resp.status_code}"
        )

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. Extract team names from the top squad tab bar
    tab_bar = soup.find("div", class_=lambda c: c and "bg-cbInactTab" in c)
    team_names = []
    if tab_bar:
        team_names = [
            d.get_text(strip=True)
            for d in tab_bar.find_all("div", class_=lambda c: c and "wb:px-2" in c)
        ]
    if len(team_names) < 2:
        team_names = ["Team 1", "Team 2"]

    # 2. Locate the squad list container
    squad_div = None
    if tab_bar and tab_bar.parent:
        pb5_divs = tab_bar.parent.find_all("div", class_=lambda c: c and "pb-5" in c)
        if pb5_divs:
            squad_div = pb5_divs[0]
    if not squad_div:
        squad_div = soup

    # 3. Two columns inside squad container: Col 0 = Team 1, Col 1 = Team 2
    two_col = squad_div.find("div", class_=lambda c: c and "w-full" in c and "flex" in c)
    cols = []
    if two_col:
        cols = [
            c for c in two_col.children
            if hasattr(c, "name") and c.name and "w-1/2" in c.get("class", [])
        ]

    teams_data = {}

    if len(cols) >= 2:
        for idx, col in enumerate(cols[:2]):
            t_name = team_names[idx] if idx < len(team_names) else f"Team {idx+1}"
            players = []
            for a in col.find_all("a", href=lambda h: h and "/profiles/" in h):
                name_span = a.find("span")
                name = name_span.get_text(strip=True) if name_span else a.get_text(strip=True)
                role_el = a.find("div", class_=lambda c: c and "text-xs" in c)
                role = role_el.get_text(strip=True) if role_el else "Unknown"
                full_text = a.get_text(separator=" ", strip=True)

                if "coach" in role.lower():
                    continue

                players.append({
                    "name": name,
                    "role": role,
                    "is_captain": "(C)" in full_text,
                    "is_wk": "(WK)" in full_text or "wk" in role.lower(),
                })
            teams_data[t_name] = players
    else:
        all_players = []
        for a in squad_div.find_all("a", href=lambda h: h and "/profiles/" in h):
            name_span = a.find("span")
            name = name_span.get_text(strip=True) if name_span else a.get_text(strip=True)
            role_el = a.find("div", class_=lambda c: c and "text-xs" in c)
            role = role_el.get_text(strip=True) if role_el else "Unknown"
            if "coach" in role.lower():
                continue
            all_players.append({
                "name": name,
                "role": role,
                "is_captain": "(C)" in a.get_text(),
                "is_wk": "(WK)" in a.get_text() or "wk" in role.lower(),
            })
        teams_data["Squad"] = all_players

    return {
        "status": "success",
        "match_id": match_id,
        "teams": teams_data,
    }


@app.get("/squads/{match_id}")
def get_match_squads(match_id: str):
    """Fetch squads and player roles for a specific match ID."""
    return extract_match_squads(match_id)


@app.get("/series/{series_id}/squads")
def get_series_squads(series_id: str):
    """Fetch squads for a series by looking up its first match."""
    series_url = f"https://www.cricbuzz.com/cricket-series/{series_id}/matches"
    resp = requests.get(series_url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Could not load series")

    match_ids = re.findall(r"/live-cricket-scores/(\d+)/", resp.text)
    if not match_ids:
        raise HTTPException(status_code=404, detail="No matches found in this series")

    first_match_id = match_ids[0]
    result = extract_match_squads(first_match_id)
    result["series_id"] = series_id
    return result
