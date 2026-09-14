import os
import re
import json
from urllib.parse import urlparse, urlunparse
import pandas as pd
import streamlit as st
import requests
import streamlit.components.v1 as components
st.set_page_config(page_title="ProductGap — Find What Competitors Miss", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container {
    max-width: 1120px;
    padding-top: 4.5rem !important;
    padding-bottom: 4rem;
}

h1 {
    font-size: 3.1rem !important;
    letter-spacing: -0.045em;
}

.pg-muted {
    color: #9aa3b2;
    font-size: 1.02rem;
    line-height: 1.65;
}

.pg-eyebrow {
    font-size: .78rem;
    letter-spacing: .13em;
    font-weight: 700;
    text-transform: uppercase;
    color: #9aa3b2;
}

.pg-good {
    padding: 14px 16px;
    border-radius: 12px;
    background: rgba(46,160,94,.13);
    border: 1px solid rgba(46,160,94,.28);
}

.pg-warn {
    padding: 14px 16px;
    border-radius: 12px;
    background: rgba(230,166,30,.10);
    border: 1px solid rgba(230,166,30,.25);
}

/* Premium ProductGap purchase card */
.offer-kicker {
    display: inline-flex;
    align-items: center;
    padding: 7px 12px;
    margin-bottom: 14px;
    border-radius: 999px;
    background: rgba(115,87,255,0.11);
    border: 1px solid rgba(115,87,255,0.28);
    color: #a99aff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .08em;
}

.offer-price {
    font-size: 44px;
    font-weight: 800;
    letter-spacing: -0.04em;
    margin-top: 14px;
}

.offer-price-note {
    color: #9aa3b2;
    font-size: 14px;
    margin-bottom: 20px;
}

.benefit-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin: 20px 0 24px 0;
}

.benefit {
    padding: 12px 13px;
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    color: #d8dce6;
    font-size: 13px;
}

.trust-line {
    color: #919aaa;
    font-size: 13px;
    text-align: center;
    margin-top: 10px;
}

.checkout-next-step {
    color: #919aaa;
    font-size: 13px;
    text-align: center;
    margin-top: 6px;
}

/* Stable button styling: no transforms/backdrop filters that can flicker on scroll. */
[data-testid="stLinkButton"] > a {
    background: linear-gradient(
        135deg,
        #7357ff 0%,
        #4d7cff 55%,
        #2997ff 100%
    ) !important;
    color: white !important;
    border: 0 !important;
    border-radius: 14px !important;
    min-height: 54px;
    font-size: 16px !important;
    font-weight: 700 !important;
    box-shadow: 0 12px 30px rgba(73,92,255,0.28);
}

[data-testid="stLinkButton"] > a:hover {
    box-shadow: 0 14px 34px rgba(73,92,255,0.36);
}

[data-testid="stButton"] > button {
    min-height: 50px;
    border-radius: 14px !important;
}

.stButton button[kind="primary"] {
    background: linear-gradient(
        135deg,
        #7357ff 0%,
        #4d7cff 55%,
        #2997ff 100%
    ) !important;
    color: white !important;
    border: 0 !important;
    border-radius: 14px !important;
    min-height: 54px;
    font-size: 16px !important;
    font-weight: 700 !important;
    box-shadow: 0 12px 30px rgba(73,92,255,0.28);
}

/* Hide Streamlit heading anchor/link icons */
.stHeading a {
    display: none !important;
}

@media (max-width: 700px) {
    .block-container {
        padding-top: 2.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    h1 {
        font-size: 2.35rem !important;
    }

    .benefit-grid {
        grid-template-columns: 1fr;
    }

    .offer-price {
        font-size: 38px;
    }
}
</style>
""", unsafe_allow_html=True)

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

OPENAI_API_KEY = secret("OPENAI_API_KEY")
BETA_ACCESS_CODE = secret("BETA_ACCESS_CODE")
SUPPORT_EMAIL = secret("SUPPORT_EMAIL", "")
PRODUCT_PRICE = secret("PRODUCT_PRICE", "$9")
MODEL = secret("PRODUCTGAP_MODEL", "gpt-5.6-luna")
PADDLE_API_KEY = secret("PADDLE_API_KEY")
PADDLE_PRICE_ID = secret("PADDLE_PRICE_ID")
PADDLE_CLIENT_TOKEN = secret("PADDLE_CLIENT_TOKEN")
PADDLE_ENVIRONMENT = secret("PADDLE_ENVIRONMENT", "sandbox").strip().lower()
if PADDLE_ENVIRONMENT not in {"sandbox", "live"}:
    PADDLE_ENVIRONMENT = "sandbox"
APP_URL = secret("APP_URL", "https://marketgap-ai.streamlit.app").rstrip("/")

SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_SECRET_KEY = secret("SUPABASE_SECRET_KEY")

checkout_mode = st.query_params.get("checkout") == "1"
SOURCE_QUALITY = {
    "retailer_review":1.0, "marketplace_review":1.0, "professional_review":0.82,
    "forum":0.65, "reddit":0.65, "manufacturer":0.52, "blog":0.55, "other":0.45
}
THEME_ALIASES = {
    "clean":"Cleaning / hygiene","hygiene":"Cleaning / hygiene","mold":"Cleaning / hygiene","slime":"Cleaning / hygiene",
    "battery":"Battery / power","charging":"Battery / power","pump":"Pump / core mechanism","motor":"Pump / core mechanism",
    "flow":"Pump / core mechanism","noise":"Noise / vibration","vibration":"Noise / vibration","replacement":"Replacement parts",
    "filter":"Replacement parts","durability":"Durability","break":"Durability","leak":"Leaks / sealing","seal":"Leaks / sealing",
    "fit":"Fit / size","size":"Fit / size","assembly":"Assembly / maintenance","maintenance":"Assembly / maintenance",
    "app":"Software / connectivity","wifi":"Software / connectivity","bluetooth":"Software / connectivity",
    "frozen":"Frozen-ingredient performance","ice":"Frozen-ingredient performance","edge":"Edge / geometry handling",
    "corner":"Edge / geometry handling","suction":"Adhesion / safety","tether":"Adhesion / safety"
}

def canonical_theme(theme):
    low = str(theme).lower()
    for needle, canonical in THEME_ALIASES.items():
        if needle in low:
            return canonical
    return re.sub(r"\s+"," ",str(theme)).strip()[:74] or "Other"

def normalize_url(url):
    try:
        p=urlparse(str(url).strip())
        return urlunparse((p.scheme.lower(),p.netloc.lower().replace("www.",""),p.path.rstrip("/"),"","",""))
    except Exception:
        return str(url)

def valid_url(url):
    return bool(re.match(r"^https?://",str(url).strip()))

def clean_json(txt):
    txt=(txt or "").strip()
    txt=re.sub(r"^```(?:json)?\s*","",txt,flags=re.I)
    txt=re.sub(r"\s*```$","",txt)
    a,b=txt.find("{"),txt.rfind("}")
    if a>=0 and b>a: txt=txt[a:b+1]
    return json.loads(txt)

def collect_urls(obj):
    found=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k=="url" and isinstance(v,str) and v.startswith(("http://","https://")): found.append(v)
                else: walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj)
    out=[]; seen=set()
    for u in found:
        n=normalize_url(u)
        if n not in seen: seen.add(n); out.append(u)
    return out

def prompt_for(products):
    block="\n".join(f"- Competitor {i+1}: {u}" for i,u in enumerate(products))
    return f"""
You are ProductGap, an evidence-first ecommerce product opportunity analyst.

COMPETING PRODUCT URLs:
{block}

First infer the actual common product category. If these products are not reasonably comparable, return:
{{"input_valid": false, "input_error": "plain-language explanation"}}

If valid, research the exact products and category using public web search.

PURPOSE:
Help a prospective ecommerce/private-label seller decide what customers still want existing products to do better.

RULES:
- Never claim a complete review scrape.
- Never invent sales, search volume, market share, review counts, prices, or frequencies.
- Numeric facts must be explicitly supported.
- Paraphrase customer feedback.
- Prefer retailer/marketplace reviews and independent professional testing.
- Search for corroboration across independent domains where practical.
- Separate recurring ownership pain from personal preference.
- Be willing to say the opportunity is weak.
- Return JSON only.

RETURN:
{{
  "input_valid": true,
  "category": "...",
  "executive_summary": "...",
  "market": {{
    "demand_strength": 1,
    "competition_intensity": 1,
    "differentiation_room": 1,
    "price_headroom": 1,
    "data_confidence": 1,
    "verdict": "strong|promising|mixed|weak",
    "rationale": "..."
  }},
  "evidence": [
    {{
      "competitor": "...",
      "theme": "...",
      "observation": "...",
      "severity": 1,
      "recurrence": "strong|moderate|weak",
      "source_type": "retailer_review|marketplace_review|professional_review|forum|reddit|manufacturer|blog|other",
      "source_url": "https://..."
    }}
  ],
  "opportunities": [
    {{
      "name": "specific product concept",
      "buyer_problem": "...",
      "target_buyer": "...",
      "evidence_themes": ["..."],
      "why_it_might_win": "...",
      "recommended_changes": ["..."],
      "positioning": "...",
      "commercial_fit": 1,
      "feasibility": 1,
      "premium_potential": 1,
      "competition_gap": 1,
      "validation_tests": ["..."],
      "kill_conditions": ["..."]
    }}
  ]
}}
All 1-5 fields must be integers. Return 2-4 opportunities only if evidence supports them.
"""

def run_research(products):
    from openai import OpenAI
    client=OpenAI(api_key=OPENAI_API_KEY)
    resp=client.responses.create(
        model=MODEL,
        tools=[{"type":"web_search","search_context_size":"medium"}],
        include=["web_search_call.action.sources"],
        input=prompt_for(products),
    )
    data=clean_json(resp.output_text)
    try: dump=resp.model_dump()
    except Exception: dump={}
    return data,collect_urls(dump)

def evidence_table(data,sources):
    source_norm={normalize_url(x) for x in sources}
    source_domains={urlparse(x).netloc.lower().replace("www.","") for x in sources}
    rows=[]
    for e in data.get("evidence",[]):
        src=e.get("source_url","")
        dom=urlparse(src).netloc.lower().replace("www.","") if src else ""
        verified=normalize_url(src) in source_norm or (dom and dom in source_domains)
        try: sev=max(1,min(5,int(e.get("severity",3))))
        except: sev=3
        rec=str(e.get("recurrence","weak")).lower()
        rec_w={"strong":1.0,"moderate":0.7,"weak":0.4}.get(rec,.4)
        sq=SOURCE_QUALITY.get(str(e.get("source_type","other")).lower(),.45)
        rows.append({
            "Competitor":e.get("competitor",""),"Theme":canonical_theme(e.get("theme","")),
            "Observation":e.get("observation",""),"Severity":sev,"Recurrence":rec.title(),
            "Source":src,"Source domain":dom,"Verified":verified,"Weight":rec_w*sq*(1 if verified else .65)
        })
    return pd.DataFrame(rows)

def market_score(m):
    def v(k):
        try:return max(1,min(5,int(m.get(k,3))))
        except:return 3
    d,c,df,p,cf=v("demand_strength"),v("competition_intensity"),v("differentiation_room"),v("price_headroom"),v("data_confidence")
    return round(d*6+(6-c)*4+df*4+p*3+cf*3)

def theme_scores(evdf):
    if evdf.empty:return {}
    ncomp=max(evdf["Competitor"].nunique(),1); out={}
    for theme,g in evdf.groupby("Theme"):
        breadth=g["Competitor"].nunique()/ncomp
        domains=len(set(d for d in g["Source domain"] if d))
        avg_sev=g["Severity"].mean()
        out[theme]=min(100,round(30*breadth+20*avg_sev/5+min(20,domains*6)+min(30,g["Weight"].sum()*8)))
    return out

def ranked_ops(data,evdf,mscore):
    ts=theme_scores(evdf); default=max(ts.values()) if ts else 40; rows=[]
    for o in data.get("opportunities",[]):
        themes=[canonical_theme(x) for x in o.get("evidence_themes",[])]
        matched=[ts[t] for t in themes if t in ts]
        escore=round(sum(matched)/len(matched)) if matched else default
        def five(k):
            try:return max(1,min(5,int(o.get(k,3))))
            except:return 3
        product=.35*five("commercial_fit")*20+.25*five("feasibility")*20+.2*five("premium_potential")*20+.2*five("competition_gap")*20
        final=round(.45*escore+.25*mscore+.30*product)
        rows.append({
            "name":o.get("name","Product opportunity"),"score":final,"target":o.get("target_buyer",""),
            "problem":o.get("buyer_problem",""),"why":o.get("why_it_might_win",""),
            "changes":o.get("recommended_changes",[]),"positioning":o.get("positioning",""),
            "tests":o.get("validation_tests",[]),"kills":o.get("kill_conditions",[])
        })
    return sorted(rows,key=lambda x:x["score"],reverse=True)

def verdict(score):
    if score>=80:return "STRONG — DEEP VALIDATION"
    if score>=75:return "GO TO VALIDATION"
    if score>=60:return "PROMISING — VALIDATE"
    return "DO NOT BUILD YET"

def report_text(data,mscore,ops,sources):
    lines=["# ProductGap Opportunity Report","",f"Category: {data.get('category','Unknown')}",f"Market score: {mscore}/100","",
           "## Executive summary",data.get("executive_summary",""),""]
    if ops:
        b=ops[0]
        lines += [f"## #1 Opportunity — {b['name']} ({b['score']}/100)",f"Verdict: {verdict(b['score'])}",
                  f"Target buyer: {b['target']}",f"Buyer problem: {b['problem']}",f"Why it might win: {b['why']}",
                  f"Positioning: {b['positioning']}","","Recommended changes:"]
        lines += [f"- {x}" for x in b["changes"]]
        lines += ["","Validation tests:"]+[f"- {x}" for x in b["tests"]]
        lines += ["","Kill conditions:"]+[f"- {x}" for x in b["kills"]]
    lines += ["","## Limitation","Publicly indexed web research; not a complete review scrape or guarantee of commercial success.",
              "","## Sources surfaced"]+[f"- {x}" for x in sources[:50]]
    return "\n".join(lines)

st.markdown('<div class="pg-eyebrow">Product opportunity intelligence</div>',unsafe_allow_html=True)
st.title("Find what your competitors missed.")
st.markdown('<p class="pg-muted">Paste 3 competing products. ProductGap researches public customer evidence, finds recurring complaints and unmet needs, and turns them into ranked product opportunities.</p>',unsafe_allow_html=True)

a,b,c=st.columns(3)
a.markdown("**① Paste competitors**\n\nThree comparable product URLs.")
b.markdown("**② Research the market**\n\nCustomer pain, demand proxies and competition.")
c.markdown("**③ Get a verdict**\n\nWhat to build differently and what could kill the idea.")
st.divider()

def supabase_headers():
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def verify_paddle_transaction(transaction_id):
    if not PADDLE_API_KEY or not PADDLE_PRICE_ID:
        return False

    if not transaction_id or not str(transaction_id).startswith("txn_"):
        return False

    api_base = (
        "https://sandbox-api.paddle.com"
        if PADDLE_ENVIRONMENT == "sandbox"
        else "https://api.paddle.com"
    )

    try:
        response = requests.get(
            f"{api_base}/transactions/{transaction_id}",
            headers={"Authorization": f"Bearer {PADDLE_API_KEY}"},
            timeout=10,
        )
        response.raise_for_status()
        transaction = response.json().get("data", {})

        # Paddle can briefly return "paid" before the transaction finishes
        # internal processing, so both paid and completed are valid here.
        if transaction.get("status") not in {"paid", "completed"}:
            return False

        purchased_price_ids = {
            item.get("price", {}).get("id")
            for item in transaction.get("items", [])
        }
        return PADDLE_PRICE_ID in purchased_price_ids

    except requests.RequestException as error:
        print(f"Paddle verification failed: {type(error).__name__}")
        return False
    except (TypeError, ValueError, KeyError) as error:
        print(f"Paddle verification response error: {type(error).__name__}")
        return False


def ensure_analysis_credit(transaction_id):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return False

    if not transaction_id or not str(transaction_id).startswith("txn_"):
        return False

    try:
        response = requests.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/analysis_credits",
            headers={
                **supabase_headers(),
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            params={"on_conflict": "transaction_id"},
            json={
                "transaction_id": transaction_id,
                "price_id": PADDLE_PRICE_ID,
                "paddle_environment": PADDLE_ENVIRONMENT,
                "analyses_allowed": 1,
                "analyses_used": 0,
            },
            timeout=10,
        )

        if response.status_code in {200, 201, 204}:
            return True

        print(
            "Supabase credit creation failed: "
            f"HTTP {response.status_code} {response.text[:500]}"
        )
        return False

    except requests.RequestException as error:
        print(f"Supabase credit connection failed: {type(error).__name__}")
        return False


def get_analysis_credit(transaction_id):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY or not transaction_id:
        return None

    try:
        response = requests.get(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/analysis_credits",
            headers=supabase_headers(),
            params={
                "transaction_id": f"eq.{transaction_id}",
                "select": (
                    "transaction_id,"
                    "price_id,"
                    "paddle_environment,"
                    "analyses_allowed,"
                    "analyses_used,"
                    "created_at,"
                    "used_at"
                ),
            },
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if rows else None

    except requests.RequestException as error:
        print(f"Supabase credit read failed: {type(error).__name__}")
        return None
    except (TypeError, ValueError, IndexError):
        return None


def claim_analysis_credit(transaction_id):
    """Atomically consume one ProductGap analysis credit."""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY or not transaction_id:
        return False

    try:
        response = requests.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/claim_analysis_credit",
            headers=supabase_headers(),
            json={"p_transaction_id": transaction_id},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()

        # PostgREST normally returns a JSON scalar for this function,
        # but handle a one-item list defensively as well.
        if isinstance(result, list) and len(result) == 1:
            result = result[0]

        return result is True

    except requests.RequestException as error:
        print(f"Supabase credit claim failed: {type(error).__name__}")
        return False
    except (TypeError, ValueError):
        return False


def show_support_hint():
    if SUPPORT_EMAIL:
        st.caption(f"Support: {SUPPORT_EMAIL}")


if "authorized" not in st.session_state:
    st.session_state.authorized = False
if "access_source" not in st.session_state:
    st.session_state.access_source = None
if "purchase_transaction_id" not in st.session_state:
    st.session_state.purchase_transaction_id = None

transaction_id = st.query_params.get("txn")
if isinstance(transaction_id, list):
    transaction_id = transaction_id[-1] if transaction_id else None

# A verified, unused Paddle transaction is the paid entitlement.
if transaction_id and not st.session_state.authorized:
    if verify_paddle_transaction(transaction_id):
        if ensure_analysis_credit(transaction_id):
            credit = get_analysis_credit(transaction_id)

            if (
                credit
                and credit.get("analyses_used", 0)
                < credit.get("analyses_allowed", 0)
            ):
                st.session_state.authorized = True
                st.session_state.access_source = "transaction"
                st.session_state.purchase_transaction_id = transaction_id
            elif credit:
                st.warning(
                    "This purchase's ProductGap analysis credit has already been used."
                )
            else:
                st.error(
                    "Your payment was verified, but ProductGap could not load the analysis credit."
                )
                show_support_hint()
        else:
            st.error(
                "Your payment was verified, but ProductGap could not create the analysis credit."
            )
            show_support_hint()
    else:
        st.error(
            "ProductGap could not verify this Paddle transaction yet. "
            "If you just completed checkout, refresh this page once."
        )
        show_support_hint()

# Checkout must be handled before the ordinary paywall.
if not st.session_state.authorized and checkout_mode:
    if not PADDLE_CLIENT_TOKEN or not PADDLE_PRICE_ID:
        st.error("Checkout is not configured yet.")
        show_support_hint()
        st.stop()

    st.subheader("ProductGap — One Market Analysis")
    checkout_caption = (
        f"Secure {PRODUCT_PRICE} test checkout powered by Paddle."
        if PADDLE_ENVIRONMENT == "sandbox"
        else f"Secure {PRODUCT_PRICE} checkout powered by Paddle."
    )
    st.caption(checkout_caption)

    paddle_environment_js = (
        'Paddle.Environment.set("sandbox");'
        if PADDLE_ENVIRONMENT == "sandbox"
        else ""
    )

    checkout_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
</head>

<body style="margin:0; background:#0e1117;">
    <div class="checkout-container"></div>

    <script>
        {paddle_environment_js}

        Paddle.Initialize({{
            token: "{PADDLE_CLIENT_TOKEN}",

            checkout: {{
                settings: {{
                    displayMode: "inline",
                    frameTarget: "checkout-container",
                    frameInitialHeight: "450",
                    frameStyle: "width: 100%; min-width: 312px; background-color: transparent; border: none;",
                    variant: "one-page"
                }}
            }},

            eventCallback: function(event) {{
                if (event.name === "checkout.completed") {{
                    const transactionId = event.data.transaction_id;

                    const continueUrl =
                        "{APP_URL}/?txn=" +
                        encodeURIComponent(transactionId);

                    document.body.innerHTML = `
                        <div style="
                            font-family: Arial, sans-serif;
                            text-align: center;
                            padding: 60px 20px;
                            color: white;
                            background: #0e1117;
                            min-height: 450px;
                        ">
                            <div style="
                                font-size: 64px;
                                margin-bottom: 20px;
                            ">✓</div>

                            <h2>Payment successful</h2>

                            <p style="
                                color: #aaaaaa;
                                margin-bottom: 30px;
                            ">
                                Your ProductGap analysis credit is ready.
                            </p>

                            <a
                                href="${{continueUrl}}"
                                target="_blank"
                                rel="noopener"
                                style="
                                    display: inline-block;
                                    padding: 14px 28px;
                                    background: linear-gradient(135deg, #7357ff, #2997ff);
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 10px;
                                    font-weight: 700;
                                "
                            >
                                Continue to ProductGap
                            </a>
                        </div>
                    `;
                }}
            }}
        }});

        Paddle.Checkout.open({{
            items: [
                {{
                    priceId: "{PADDLE_PRICE_ID}",
                    quantity: 1
                }}
            ]
        }});
    </script>
</body>
</html>
"""

    components.html(checkout_html, height=650, scrolling=False)
    st.stop()


if not st.session_state.authorized:
    st.markdown(
        """
        <div class="offer-kicker">
            PRODUCT OPPORTUNITY ANALYSIS
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        spacer_left, main, spacer_right = st.columns([0.12, 1, 0.12])

        with main:
            st.markdown("## Find the opportunity your competitors missed.")

            st.write(
                "Paste 3 competing products and get an evidence-backed market report "
                "built from public customer complaints, unmet needs and competitive signals."
            )

            st.markdown(
                f"""
                <div class="offer-price">{PRODUCT_PRICE}</div>
                <div class="offer-price-note">
                    One-time purchase • One market analysis
                </div>

                <div class="benefit-grid">
                    <div class="benefit">✓ Customer pain signals</div>
                    <div class="benefit">✓ Ranked opportunities</div>
                    <div class="benefit">✓ Positioning ideas</div>
                    <div class="benefit">✓ Validation tests</div>
                    <div class="benefit">✓ Kill conditions</div>
                    <div class="benefit">✓ Downloadable report</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.link_button(
                f"Analyze my market — {PRODUCT_PRICE} →",
                f"{APP_URL}/?checkout=1",
                use_container_width=True,
            )

            st.markdown(
                """
                <div class="trust-line">
                    Secure one-time checkout · Powered by Paddle
                </div>
                <div class="checkout-next-step">
                    After checkout, return here and paste 3 competing product URLs.
                </div>
                """,
                unsafe_allow_html=True,
            )

            if BETA_ACCESS_CODE:
                with st.expander("Have an access code?"):
                    code = st.text_input(
                        "Access code",
                        type="password",
                        placeholder="Enter access code",
                    )

                    if st.button(
                        "Use access code",
                        use_container_width=True,
                        key="use_access_code",
                    ):
                        if code == BETA_ACCESS_CODE:
                            st.session_state.authorized = True
                            st.session_state.access_source = "access_code"
                            st.session_state.purchase_transaction_id = None
                            st.rerun()
                        else:
                            st.error("That access code is not valid.")

    st.stop()

if not OPENAI_API_KEY:
    st.error("ProductGap is not configured. Add OPENAI_API_KEY to the server secrets.")
    st.stop()

st.subheader("Analyze a market")
st.caption("Use three competing products that solve roughly the same problem. ProductGap infers the category automatically.")

with st.form("form"):
    u1=st.text_input("Competitor 1 URL",placeholder="https://...")
    u2=st.text_input("Competitor 2 URL",placeholder="https://...")
    u3=st.text_input("Competitor 3 URL",placeholder="https://...")
    agree=st.checkbox("I understand this is decision-support research, not a guarantee of product success.")
    submitted=st.form_submit_button("Analyze market",type="primary",use_container_width=True)

if submitted:
    products = [x.strip() for x in [u1, u2, u3] if x.strip()]

    if len(products) != 3 or not all(valid_url(x) for x in products):
        st.error("Enter 3 valid http/https product URLs.")
        st.stop()

    if not agree:
        st.error("Please confirm the research limitation.")
        st.stop()

    paid_transaction_id = st.session_state.get("purchase_transaction_id")
    paid_access = st.session_state.get("access_source") == "transaction"

    # Block a second analysis before spending another OpenAI request.
    if paid_access:
        credit = get_analysis_credit(paid_transaction_id)
        if not credit:
            st.error("ProductGap could not load your analysis credit.")
            show_support_hint()
            st.stop()

        if credit.get("analyses_used", 0) >= credit.get("analyses_allowed", 0):
            st.error(
                "This purchase's analysis credit has already been used. "
                "Purchase another analysis to research a new market."
            )
            st.stop()

    with st.status("Researching competitors…", expanded=True) as s:
        st.write("Finding product-specific customer evidence and independent sources.")
        st.write("Evaluating demand proxies, competition, recurring pain and differentiation.")

        try:
            data, sources = run_research(products)
        except Exception as error:
            print(f"Research failed: {type(error).__name__}")
            s.update(label="Research failed", state="error")
            st.error("The analysis could not be completed. Please try again later.")
            show_support_hint()
            st.stop()

        if not data.get("input_valid", True):
            s.update(label="Products are not comparable", state="error")
            st.error(data.get("input_error", "These products are not comparable."))
            st.stop()

        # Only consume the paid credit after ProductGap has completed a valid
        # research run. Access-code sessions intentionally bypass paid credits.
        if paid_access:
            if not claim_analysis_credit(paid_transaction_id):
                s.update(label="Analysis credit unavailable", state="error")
                st.error(
                    "This analysis credit has already been used or could not be claimed."
                )
                show_support_hint()
                st.stop()

        s.update(label="Research complete", state="complete")

    evdf = evidence_table(data, sources)
    mscore = market_score(data.get("market", {}))
    ops = ranked_ops(data, evdf, mscore)

    if not ops:
        st.warning(
            "No defensible product opportunity was found from the available evidence. "
            "That is still the result of this completed market analysis."
        )
        st.markdown(f"**Category:** {data.get('category', 'Unknown')}")
        st.write(data.get("executive_summary", ""))
        st.stop()

    best = ops[0]
    x, y, z = st.columns(3)
    x.metric("Market score", f"{mscore}/100")
    y.metric("Evidence observations", len(evdf))
    z.metric("Best opportunity", f"{best['score']}/100")

    css = "pg-good" if best["score"] >= 60 else "pg-warn"
    st.markdown(
        f'<div class="{css}"><b>{verdict(best["score"])}</b><br>'
        f'<span style="font-size:1.2rem;font-weight:700">#1 {best["name"]}</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Why this opportunity exists")
    st.write(best["why"])
    st.markdown(f"**Target buyer:** {best['target']}")
    st.markdown(f"**Positioning:** {best['positioning']}")

    t1, t2, t3 = st.tabs(["Opportunity", "Evidence", "Market"])

    with t1:
        st.markdown("#### What to change")
        for item in best["changes"]:
            st.write("•", item)

        st.markdown("#### Validate before investing")
        for item in best["tests"]:
            st.write("•", item)

        st.markdown("#### Kill the idea if…")
        for item in best["kills"]:
            st.write("•", item)

        for i, opportunity in enumerate(ops[1:], start=2):
            with st.expander(
                f"#{i} {opportunity['name']} — {opportunity['score']}/100"
            ):
                st.write(opportunity["why"])
                st.markdown(f"**Positioning:** {opportunity['positioning']}")

    with t2:
        if evdf.empty:
            st.info("No detailed evidence trail was returned.")
        else:
            for theme, group in evdf.groupby("Theme"):
                domains = len(set(d for d in group["Source domain"] if d))
                with st.expander(
                    f"{theme} — {len(group)} observations · {domains} source domains"
                ):
                    for _, row in group.iterrows():
                        st.write(f"**{row['Competitor']}** — {row['Observation']}")
                        if row["Source"]:
                            st.caption(row["Source"])

    with t3:
        market = data.get("market", {})
        cols = st.columns(5)
        labels = [
            ("Demand", "demand_strength"),
            ("Competition", "competition_intensity"),
            ("Differentiation", "differentiation_room"),
            ("Price room", "price_headroom"),
            ("Confidence", "data_confidence"),
        ]

        for col, (label, key) in zip(cols, labels):
            col.metric(label, f"{market.get(key, '?')}/5")

        st.write(market.get("rationale", ""))
        st.markdown(f"**Category:** {data.get('category', 'Unknown')}")

    report = report_text(data, mscore, ops, sources)
    st.download_button(
        "Download full opportunity report",
        report.encode("utf-8"),
        file_name="productgap_opportunity_report.md",
        mime="text/markdown",
        use_container_width=True,
        on_click="ignore",
    )
    st.caption(
        "ProductGap uses publicly indexed evidence and does not claim to scrape every customer review."
    )
