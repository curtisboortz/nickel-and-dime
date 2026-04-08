# Reddit Launch Posts

Use one per day, not all at once. Wait until you've built karma in each subreddit.

---

## r/SideProject

**Title:** I built a portfolio tracker for macro investors — 6 months of solo dev

**Body:**

Hey r/SideProject,

I've been building Nickel & Dime for about 6 months. It's a portfolio tracker designed for self-directed investors who follow macro data.

The problem I was solving: every morning I'd check my brokerage, then FRED for yield curves, then Twitter for gold prices, then a spreadsheet for net worth. Five tools for one question — "how is my portfolio positioned?"

What it does:
- Live market pulse (gold, silver, BTC, yields, DXY, VIX — updates every 5 min)
- Portfolio tracker for stocks, ETFs, crypto, physical metals
- FRED economic data (yield curves, CPI, unemployment, GDP)
- Sentiment gauges (Fear & Greed, CAPE ratio, Buffett Indicator)
- AI advisor that analyzes your portfolio through different investment frameworks
- Budget manager

Tech stack: Flask/Python backend, vanilla JS frontend, PostgreSQL, deployed on Railway. Mobile app via Capacitor (iOS + Android).

Free tier available, Pro is $12/month. Would love feedback from other builders.

---

## r/startups

**Title:** Launching Nickel & Dime — the portfolio tracker that shows your money in the context of the economy

**Body:**

After 6 months of solo development, I'm launching Nickel & Dime — a portfolio tracking dashboard built for investors who follow macro data.

**The gap I found:** Existing portfolio trackers (Empower, Kubera) show your money in isolation. If you're the kind of investor who reads Fed minutes, watches yield curves, and tracks gold/silver ratios, you need those data points next to your portfolio — not in a separate tab.

**What Nickel & Dime does differently:**
1. Live FRED data (yield curves, CPI, GDP) alongside your holdings
2. Sentiment gauges (Fear & Greed, CAPE, Buffett Indicator, Sahm Rule)
3. Custom pulse cards with ratio support (gold/silver, gold/oil)
4. AI advisor using Dalio/Graham/Bogle frameworks with your actual data
5. Physical metals tracking (gold, silver by weight/purity)

**Business model:** Free tier for market data, $12/month Pro for portfolio tracking + AI. No ads, no data selling.

**Target market:** Self-directed investors who follow macro trends. Think r/Gold, r/Bogleheads, FinTwit.

Just launched on Product Hunt — would appreciate any feedback on positioning or features.

---

## r/Gold

**Title:** I built a free tool that tracks gold/silver ratios alongside your portfolio

**Body:**

Hey r/Gold,

I'm a gold/silver investor myself and I got tired of manually calculating ratios and checking FRED for macro data in separate tabs while trying to manage my portfolio.

So I built Nickel & Dime — it's a portfolio tracker with a built-in macro dashboard. The features most relevant to this community:

- Gold/silver ratio as a live pulse card (updates every 5 min)
- Physical metals tracking by weight and purity (not just ETFs)
- Live gold, silver, platinum, palladium prices
- FRED yield curve data (relevant for predicting Fed moves that affect metals)
- DXY tracking (inverse correlation with gold)
- CNN Fear & Greed and VIX (risk sentiment context)

The market pulse and economics features are free. Portfolio tracking is $12/month with a 14-day trial.

Not trying to hard-sell — genuinely built this for investors like us. Happy to hear feedback.

---

## r/Bogleheads

**Title:** I made a portfolio template comparison tool — All-Weather, 60/40, Permanent Portfolio side by side against your actual holdings

**Body:**

Hi r/Bogleheads,

I know this community values simplicity and evidence-based investing, so I want to share something I built that might be useful: a portfolio template comparison feature.

You can overlay your actual allocation against:
- Classic 60/40
- All-Weather (Dalio)
- Permanent Portfolio (Harry Browne)
- Three-Fund Portfolio

It shows you exactly where your allocation diverges from each template, with a radar chart comparison and specific percentages.

This is part of Nickel & Dime, a portfolio tracker I've been building. The template comparison is available on the Pro tier ($12/month, 14-day free trial). The free tier includes live market data, economic calendar, and sentiment gauges.

Not a replacement for your brokerage app — more of a complement for the macro-aware Boglehead who wants their portfolio in the context of economic data.

Interested in honest feedback from this community.
