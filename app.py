
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
h1 {font-size: 3.1rem !important; letter-spacing: -0.045em;}
.pg-muted {color:#8d96a5; font-size:1.02rem;}
.pg-eyebrow {font-size:.78rem; letter-spacing:.13em; font-weight:700; text-transform:uppercase; color:#8d96a5;}
.pg-good {padding:14px 16px; border-radius:12px; background:rgba(46,160,94,.13); border:1px solid rgba(46,160,94,.28);}
.pg-warn {padding:14px 16px; border-radius:12px; background:rgba(230,166,30,.10); border:1px solid rgba(230,166,30,.25);}
</style>
""", unsafe_allow_html=True)

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

OPENAI_API_KEY = secret("OPENAI_API_KEY")
BETA_ACCESS_CODE = secret("BETA_ACCESS_CODE")
PAYMENT_URL = secret("PAYMENT_URL")
SUPPORT_EMAIL = secret("SUPPORT_EMAIL", "")
PRODUCT_PRICE = secret("PRODUCT_PRICE", "$9")
MODEL = secret("PRODUCTGAP_MODEL", "gpt-5.6-luna")
PADDLE_RETURN_TOKEN = secret("PADDLE_RETURN_TOKEN")
PADDLE_API_KEY = secret("PADDLE_API_KEY")
PADDLE_PRICE_ID = secret("PADDLE_PRICE_ID")
PADDLE_CLIENT_TOKEN = secret("PADDLE_CLIENT_TOKEN")
APP_URL = secret("APP_URL", "https://marketgap-ai.streamlit.app")
if "authorized" not in st.session_state:
    st.session_state.authorized = False

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
st.markdown('<p class="pg-muted">Paste 3 competing products. ProductGap researches public customer evidence and turns recurring failures into ranked product opportunities.</p>',unsafe_allow_html=True)

a,b,c=st.columns(3)
a.markdown("**① Paste competitors**\n\nThree comparable product URLs.")
b.markdown("**② Research the market**\n\nCustomer pain, demand proxies and competition.")
c.markdown("**③ Get a verdict**\n\nWhat to build differently and what could kill the idea.")
st.divider()

if "authorized" not in st.session_state:
    st.session_state.authorized = False

paid_token = st.query_params.get("paid")
def verify_paddle_transaction(transaction_id):
    if not PADDLE_API_KEY or not PADDLE_PRICE_ID:
        return False

    if not transaction_id or not transaction_id.startswith("txn_"):
        return False

    try:
        response = requests.get(
            f"https://sandbox-api.paddle.com/transactions/{transaction_id}",
            headers={
                "Authorization": f"Bearer {PADDLE_API_KEY}",
            },
            timeout=10,
        )

        response.raise_for_status()
        transaction = response.json().get("data", {})

        # Paddle may briefly report "paid" before internal processing
        if transaction.get("status") not in {"paid", "completed"}:
            return False

        purchased_price_ids = {
            item.get("price", {}).get("id")
            for item in transaction.get("items", [])
        }

        return PADDLE_PRICE_ID in purchased_price_ids

    except Exception:
        return False
        
if BETA_ACCESS_CODE:
    
    # Unlock after successful Paddle sandbox redirect
    paid_token = st.query_params.get("paid")

    if PADDLE_RETURN_TOKEN and paid_token == PADDLE_RETURN_TOKEN:
        st.session_state.authorized = True
        st.query_params.clear()

    # If not authorized, show the payment/access gate and STOP the app here
    

    if not st.session_state.authorized and checkout_mode:
        st.subheader("ProductGap — Founding Beta")
        st.caption("Secure $9 test checkout powered by Paddle.")

        checkout_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
        </head>

        <body>
            <div class="checkout-container"></div>

            <script>
                Paddle.Environment.set("sandbox");

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

                    eventCallback: function(event) {
    if (event.name === "checkout.completed") {
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
                <div style="font-size:64px; margin-bottom:20px;">✓</div>
                <h2>Payment successful</h2>
                <p style="color:#aaa; margin-bottom:30px;">
                    Your ProductGap access is ready.
                </p>

                <a
                    href="${continueUrl}"
                    target="_blank"
                    style="
                        display:inline-block;
                        padding:14px 28px;
                        background:#ff4b4b;
                        color:white;
                        text-decoration:none;
                        border-radius:8px;
                        font-weight:600;
                    "
                >
                    Continue to ProductGap
                </a>
            </div>
        `;
    }
}
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

        components.html(
            checkout_html,
            height=650,
            scrolling=False
        )

        st.stop()
    if not st.session_state.authorized:
        left, right = st.columns([1.4, 1])

        with left:
            st.subheader(f"Founding Beta — {PRODUCT_PRICE}")
            st.write(
                "One full market analysis with ranked product opportunities, "
                "evidence, validation tests and a downloadable report."
            )

            st.link_button(
                f"Get beta access — {PRODUCT_PRICE}",
                f"{APP_URL}/?checkout=1",
                use_container_width=True
            )

            
        with right:
            st.subheader("Already have access?")

            code = st.text_input(
                "Access code",
                type="password",
                label_visibility="collapsed",
                placeholder="Enter beta access code",
            )

            if st.button(
                "Unlock ProductGap",
                type="primary",
                use_container_width=True,
            ):
                if code == BETA_ACCESS_CODE:
                    st.session_state.authorized = True
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
    products=[x.strip() for x in [u1,u2,u3] if x.strip()]
    if len(products)!=3 or not all(valid_url(x) for x in products):
        st.error("Enter 3 valid http/https product URLs."); st.stop()
    if not agree:
        st.error("Please confirm the research limitation."); st.stop()

    with st.status("Researching competitors…",expanded=True) as s:
        st.write("Finding product-specific customer evidence and independent sources.")
        st.write("Evaluating demand proxies, competition, recurring pain and differentiation.")
        try:data,sources=run_research(products)
        except Exception:
            s.update(label="Research failed",state="error")
            st.error("The analysis could not be completed. Please try again later.")
            if SUPPORT_EMAIL: st.caption(f"Support: {SUPPORT_EMAIL}")
            st.stop()
        if not data.get("input_valid",True):
            s.update(label="Products are not comparable",state="error")
            st.error(data.get("input_error","These products are not comparable.")); st.stop()
        s.update(label="Research complete",state="complete")

    evdf=evidence_table(data,sources)
    mscore=market_score(data.get("market",{}))
    ops=ranked_ops(data,evdf,mscore)
    if not ops:
        st.warning("No defensible opportunity was found from the available evidence."); st.stop()

    best=ops[0]
    x,y,z=st.columns(3)
    x.metric("Market score",f"{mscore}/100")
    y.metric("Evidence observations",len(evdf))
    z.metric("Best opportunity",f"{best['score']}/100")
    css="pg-good" if best["score"]>=60 else "pg-warn"
    st.markdown(f'<div class="{css}"><b>{verdict(best["score"])}</b><br><span style="font-size:1.2rem;font-weight:700">#1 {best["name"]}</span></div>',unsafe_allow_html=True)

    st.markdown("### Why this opportunity exists")
    st.write(best["why"])
    st.markdown(f"**Target buyer:** {best['target']}")
    st.markdown(f"**Positioning:** {best['positioning']}")

    t1,t2,t3=st.tabs(["Opportunity","Evidence","Market"])
    with t1:
        st.markdown("#### What to change")
        for x in best["changes"]: st.write("•",x)
        st.markdown("#### Validate before investing")
        for x in best["tests"]: st.write("•",x)
        st.markdown("#### Kill the idea if…")
        for x in best["kills"]: st.write("•",x)
        for i,o in enumerate(ops[1:],start=2):
            with st.expander(f"#{i} {o['name']} — {o['score']}/100"):
                st.write(o["why"]); st.markdown(f"**Positioning:** {o['positioning']}")
    with t2:
        if evdf.empty: st.info("No detailed evidence trail was returned.")
        else:
            for theme,g in evdf.groupby("Theme"):
                domains=len(set(d for d in g["Source domain"] if d))
                with st.expander(f"{theme} — {len(g)} observations · {domains} source domains"):
                    for _,r in g.iterrows():
                        st.write(f"**{r['Competitor']}** — {r['Observation']}")
                        if r["Source"]: st.caption(r["Source"])
    with t3:
        m=data.get("market",{})
        cs=st.columns(5)
        labels=[("Demand","demand_strength"),("Competition","competition_intensity"),("Differentiation","differentiation_room"),("Price room","price_headroom"),("Confidence","data_confidence")]
        for col,(label,key) in zip(cs,labels): col.metric(label,f"{m.get(key,'?')}/5")
        st.write(m.get("rationale",""))
        st.markdown(f"**Category:** {data.get('category','Unknown')}")

    report=report_text(data,mscore,ops,sources)
    st.download_button("Download full opportunity report",report.encode("utf-8"),file_name="productgap_opportunity_report.md",mime="text/markdown",use_container_width=True)
    st.caption("ProductGap uses publicly indexed evidence and does not claim to scrape every customer review.")
