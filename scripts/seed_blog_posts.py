"""Seed the database with 5 SEO-optimized blog posts.

Run once:  flask shell < scripts/seed_blog_posts.py
Or:        python scripts/seed_blog_posts.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

POSTS = [
    {
        "slug": "all-weather-portfolio-2026-ray-dalio-strategy",
        "title": "The All-Weather Portfolio in 2026: Is Ray Dalio's Strategy Still Relevant?",
        "excerpt": "Ray Dalio's All-Weather Portfolio was designed to perform in any economic environment. With inflation cooling, rates elevated, and geopolitical risk rising, does it still hold up in 2026?",
        "meta_description": "Is Ray Dalio's All-Weather Portfolio still relevant in 2026? We break down the strategy, its performance through recent cycles, and how to benchmark your own allocation.",
        "body": """<p>Ray Dalio's All-Weather Portfolio has been one of the most discussed investment frameworks of the last decade. Designed at Bridgewater Associates to perform across all economic environments (growth, recession, inflation, and deflation), it allocates roughly 30% to stocks, 40% to long-term bonds, 15% to intermediate bonds, 7.5% to gold, and 7.5% to commodities.</p>

<p>But 2022-2025 tested this strategy harder than any period since its popularization. With bonds and stocks falling simultaneously, the 40% bond allocation dragged performance. Gold, however, surged past $3,000/oz, validating the commodity hedge thesis.</p>

<h2>How the All-Weather Performed Through Recent Cycles</h2>

<p>From 2022 to mid-2025, the traditional All-Weather returned roughly 2.8% annualized, significantly underperforming the S&P 500's 12%+ run. Critics pointed to the heavy bond allocation as a structural weakness in a rising-rate environment.</p>

<p>However, Dalio's original thesis wasn't about maximizing returns; it was about <strong>risk parity</strong>. Each asset class should contribute equally to portfolio risk. By that measure, the All-Weather did what it promised: it avoided catastrophic drawdowns. While the S&P 500 fell 25% in 2022, the All-Weather lost only 12%.</p>

<h2>The 2026 Question: Bonds vs. Commodities</h2>

<p>With the Fed holding rates above 4%, long-term Treasuries remain under pressure. But there's a case for them: if a recession materializes, bonds rally hard. The All-Weather was designed to own them precisely for this scenario.</p>

<p>Meanwhile, the gold and commodity allocation has been the star. Gold above $3,000 and silver outperforming in late 2025 have pushed the commodity sleeve to its best stretch since 2011. The gold-to-silver ratio, which Nickel & Dime tracks as a pulse card, sits at historically elevated levels, suggesting silver may have more catch-up potential.</p>

<h2>Should You Use the All-Weather in 2026?</h2>

<p>The All-Weather remains an excellent <em>starting point</em>, not a destination. Consider it a benchmark for your own allocation. Ask yourself:</p>

<ul>
<li>Am I overexposed to equities relative to my risk tolerance?</li>
<li>Do I have enough inflation protection (gold, TIPS, commodities)?</li>
<li>Am I holding bonds for the right reason (deflation/recession hedge)?</li>
</ul>

<p>Tools like Nickel & Dime's portfolio template comparison let you overlay your actual allocation against the All-Weather, 60/40, and Permanent Portfolio side by side, so you can see exactly where you diverge and decide if that's intentional.</p>

<h2>The Bottom Line</h2>

<p>Ray Dalio's All-Weather Portfolio isn't dead. It's doing what it was designed to do: protect capital across environments. If you're looking for maximum growth, it's the wrong framework. If you're looking for sleep-at-night diversification with macro awareness, it's still one of the best starting points for self-directed investors.</p>

<p>The key is combining a framework like this with <em>active macro awareness</em>: watching yield curves, inflation data, and sentiment indicators to understand which economic regime you're in. That context turns a static allocation into an informed strategy.</p>"""
    },
    {
        "slug": "gold-silver-ratio-explained-investors-2026",
        "title": "Gold-to-Silver Ratio Explained: What It Tells Investors in 2026",
        "excerpt": "The gold-to-silver ratio is one of the oldest market indicators. Learn what it means, how to read it, and what the current ratio tells us about precious metals in 2026.",
        "meta_description": "The gold-to-silver ratio explained for investors. Learn what the ratio means, historical context, and what it signals for precious metals investing in 2026.",
        "body": """<p>The gold-to-silver ratio measures how many ounces of silver it takes to buy one ounce of gold. At a ratio of 85, for example, gold is 85 times more expensive than silver by weight. It's one of the oldest market indicators, tracked by precious metals investors for centuries.</p>

<h2>What Does the Ratio Tell You?</h2>

<p>Historically, the ratio has averaged around 60-65 over the past 50 years. When it moves significantly above this range (above 80), it suggests silver is undervalued relative to gold. When it drops below 50, silver may be relatively expensive.</p>

<p>Key historical moments:</p>

<ul>
<li><strong>1980 (ratio ~17):</strong> The Hunt Brothers' silver squeeze pushed silver to $50/oz. The ratio hit all-time lows.</li>
<li><strong>1991 (ratio ~100):</strong> After the savings and loan crisis, silver was deeply out of favor.</li>
<li><strong>2011 (ratio ~32):</strong> Silver surged to $49/oz during the post-GFC commodity rally.</li>
<li><strong>2020 (ratio ~125):</strong> COVID panic drove gold up while silver initially crashed. The ratio hit its highest level in modern history.</li>
<li><strong>2026 (ratio ~85):</strong> Elevated but off the 2020 extremes. Gold above $3,000 has outpaced silver's recovery.</li>
</ul>

<h2>Why the Ratio Matters for Your Portfolio</h2>

<p>If you hold physical gold or silver (or ETFs like GLD/SLV), the ratio helps you think about <strong>relative value</strong>. A high ratio doesn't mean silver will definitely catch up, but historically, extreme readings have tended to mean-revert over 2-5 year periods.</p>

<p>Some investors use the ratio to swap between metals: selling gold and buying silver when the ratio is high, then reversing when it contracts. This is an advanced strategy that requires patience and conviction.</p>

<h2>How to Track the Ratio</h2>

<p>Most brokerage apps show gold and silver prices separately, but calculating the ratio requires manual math. Nickel & Dime's pulse card system lets you create a custom ratio card (gold/silver) that updates live every 5 minutes. You can also track gold/oil, gold/S&P 500, and other cross-asset ratios that macro investors care about.</p>

<h2>What the Current Ratio Signals</h2>

<p>At 85, the ratio is above its long-term average but not extreme. With industrial demand for silver rising (solar panels, EVs, electronics) and mine supply stagnant, the fundamental case for silver is arguably stronger than any time since 2011.</p>

<p>But fundamentals take time to play out. The near-term driver is monetary policy. If the Fed cuts rates, both metals benefit, but silver tends to outperform gold in rate-cutting cycles due to its higher beta and industrial demand sensitivity.</p>

<p>Watch the ratio alongside yield curves and Fed policy expectations. When real rates fall and liquidity expands, the gold-silver ratio typically contracts. That's the macro context every precious metals investor should be tracking.</p>"""
    },
    {
        "slug": "track-net-worth-across-every-account",
        "title": "How to Actually Track Your Net Worth Across Every Account",
        "excerpt": "Tracking net worth sounds simple, but most people's money is scattered across 5+ accounts. Here's how to consolidate everything into one view, and which tools actually work.",
        "meta_description": "How to track your net worth across all accounts: brokerage, bank, crypto, and physical assets. Compare Empower, Kubera, Mint, and Nickel & Dime for portfolio tracking.",
        "body": """<p>Your net worth is the single most important number in personal finance. It's the sum of everything you own minus everything you owe. Simple in concept, messy in practice.</p>

<p>The average self-directed investor has their money in 5-8 different places: a 401(k), a Roth IRA, a taxable brokerage account, a bank account, maybe a crypto exchange, and possibly physical assets like gold or real estate. Tracking all of this in one place is surprisingly hard.</p>

<h2>The Spreadsheet Problem</h2>

<p>Many investors start with a spreadsheet. It works at first: manually enter account balances monthly, track the trend. But spreadsheets break when:</p>

<ul>
<li>You forget to update for a few months</li>
<li>You want to see daily changes, not just monthly snapshots</li>
<li>You need to track individual holdings with live prices</li>
<li>You want to see your allocation breakdown (how much in stocks vs. bonds vs. gold)</li>
</ul>

<h2>Tool Comparison: What Actually Works</h2>

<h3>Empower (formerly Personal Capital)</h3>
<p>Pros: Free, solid account aggregation via Plaid, decent allocation breakdown.<br>
Cons: No macro data. No physical metals tracking. Aggressive upselling to their advisory service. The app focuses on retirement projections rather than active portfolio analysis.</p>

<h3>Kubera</h3>
<p>Pros: Comprehensive; tracks crypto, real estate, vehicles, art, and traditional accounts.<br>
Cons: $150/year is steep for individuals. No economic data integration. Designed more for high-net-worth tracking than active investment analysis.</p>

<h3>Mint (Discontinued)</h3>
<p>Mint shut down in early 2024. If you were a Mint user, you're likely still looking for a replacement that combines budgeting with portfolio tracking.</p>

<h3>Nickel & Dime</h3>
<p>Pros: Portfolio tracking + macro data in one dashboard. Live prices for stocks, ETFs, crypto, and physical metals. FRED economic data, sentiment gauges, yield curves, FedWatch probabilities. AI advisor. Budget manager. $15/month with a free tier.<br>
Cons: Newer product, smaller user base. No real estate or vehicle tracking (yet).</p>

<h2>The Right Approach</h2>

<p>Here's what we recommend:</p>

<ol>
<li><strong>Centralize your investment accounts</strong> using Plaid-based linking or CSV import to get all your brokerage accounts in one place.</li>
<li><strong>Add manual accounts</strong> for anything that can't be linked (physical gold, real estate equity, private investments).</li>
<li><strong>Track monthly</strong> at minimum. Daily if your tool supports it with live prices.</li>
<li><strong>Look at allocation, not just total</strong>: knowing you have $200K is less useful than knowing 80% of it is in tech stocks.</li>
<li><strong>Add macro context</strong>: your portfolio doesn't exist in a vacuum. Track it alongside the economic indicators that affect your holdings.</li>
</ol>

<p>The best net worth tracker is the one you actually use consistently. Pick a tool, commit to it for 3 months, and watch how much clearer your financial picture becomes.</p>"""
    },
    {
        "slug": "yield-curve-explained-practical-guide-investors",
        "title": "Understanding the Yield Curve: A Practical Guide for Investors",
        "excerpt": "The yield curve is one of the most-watched economic indicators. This guide explains what it is, what an inversion means, and how to use it in your investment decisions.",
        "meta_description": "The yield curve explained for investors. Learn what yield curve inversions mean, how to read the 2s10s spread, and what the curve is signaling in 2026.",
        "body": """<p>The yield curve is a graph showing interest rates on U.S. Treasury bonds across different maturities, from 1-month bills to 30-year bonds. In a normal economy, longer-term bonds pay higher rates than short-term ones (you're compensated for locking up money longer). When this relationship breaks down, it tells you something important about market expectations.</p>

<h2>The Three Shapes</h2>

<h3>Normal (Upward Sloping)</h3>
<p>Short-term rates are lower than long-term rates. This is the "healthy" shape: it means markets expect steady growth and gradually rising rates. Banks can profit by borrowing short (paying low rates) and lending long (earning higher rates).</p>

<h3>Flat</h3>
<p>Short-term and long-term rates are roughly equal. This often signals a transition period: the economy is slowing, and markets aren't sure which direction things are headed. It's a yellow light.</p>

<h3>Inverted (Downward Sloping)</h3>
<p>Short-term rates are <em>higher</em> than long-term rates. This is the recession warning signal. An inverted yield curve has preceded every U.S. recession since 1970, though the timing varies from 6 to 24 months.</p>

<h2>The 2s10s Spread</h2>

<p>The most-watched measure is the spread between the 2-year and 10-year Treasury yields ("2s10s"). When the 10-year yield drops below the 2-year yield, the curve is inverted. This spread went negative in mid-2022 and stayed inverted into 2024, one of the longest inversions in history.</p>

<p>The curve uninverted in 2025, which historically is <em>also</em> a warning sign. Recessions often begin not during the inversion, but after the curve steepens back to normal, a phenomenon known as the "bull steepener" signal.</p>

<h2>What the Curve Tells You About Your Portfolio</h2>

<p>As a self-directed investor, the yield curve affects you in several ways:</p>

<ul>
<li><strong>Bond allocation:</strong> In an inverted curve, short-term Treasuries and money markets can pay more than long bonds with less risk. Consider where your fixed-income allocation sits on the curve.</li>
<li><strong>Equity risk:</strong> Curve inversions precede recessions. If you're heavily allocated to cyclical stocks (financials, consumer discretionary, industrials), an inversion is a signal to review your exposure.</li>
<li><strong>Real estate:</strong> An inverted curve often means tight credit conditions, which slow housing markets.</li>
<li><strong>Gold and commodities:</strong> These tend to perform well when the curve steepens after inversion, as it often coincides with rate cuts and dollar weakness.</li>
</ul>

<h2>How to Track the Yield Curve</h2>

<p>FRED (Federal Reserve Economic Data) publishes yield curve data daily. Nickel & Dime's economics tab pulls this data directly from FRED and visualizes it alongside your portfolio, so you can see your holdings in the context of the rate environment.</p>

<p>Track the 2s10s spread, the 3-month/10-year spread (which the Fed's own recession model uses), and the full curve shape over 1-year, 5-year, and maximum timeframes. The trend matters as much as the current level.</p>

<h2>The 2026 Picture</h2>

<p>As of early 2026, the curve has normalized but remains relatively flat by historical standards. The Fed has paused rate cuts, inflation is sticky above 2%, and long-term rates reflect uncertainty about government debt levels. This is a "watch closely" environment: not a panic signal, but not an all-clear either.</p>

<p>The investors who navigate this well will be the ones who monitor the data regularly and adjust allocation proactively rather than reactively.</p>"""
    },
    {
        "slug": "5-macro-indicators-investors-should-watch-daily",
        "title": "5 Macro Indicators Every Investor Should Watch Daily",
        "excerpt": "Markets don't move in isolation. These five macro indicators give you real-time context for every investment decision, and most investors ignore at least two of them.",
        "meta_description": "5 macro indicators every investor should watch daily: VIX, yield curve, gold/silver ratio, Fear & Greed index, and DXY. How to track them all in one dashboard.",
        "body": """<p>Most investors check their portfolio daily but ignore the macro backdrop. That's like checking the score of a game without knowing what quarter it is, what the weather conditions are, or who's injured. These five indicators give you the context your portfolio needs.</p>

<h2>1. The VIX (Volatility Index)</h2>

<p>The VIX measures expected volatility in the S&P 500 over the next 30 days. It's often called the "fear gauge."</p>

<ul>
<li><strong>Below 15:</strong> Markets are calm, possibly complacent. Historically a good time to buy protection (cheap options).</li>
<li><strong>15-20:</strong> Normal range. Markets are functioning normally with typical uncertainty.</li>
<li><strong>20-30:</strong> Elevated fear. Stocks are likely choppy. Not necessarily time to sell, but time to pay attention.</li>
<li><strong>Above 30:</strong> Panic territory. Major events are unfolding. These spikes are often short-lived and historically have been good long-term buying opportunities.</li>
</ul>

<p>Track the VIX daily. It's the market's real-time risk thermometer.</p>

<h2>2. The 10-Year Treasury Yield</h2>

<p>The 10-year yield is the benchmark rate for the global financial system. It affects mortgage rates, corporate borrowing costs, stock valuations, and the dollar. When it rises, it puts pressure on growth stocks (their future cash flows are worth less in present value). When it falls, it signals either rate cuts or a flight to safety.</p>

<p>Watch the <em>direction</em> more than the absolute level. A 10-year yield rising from 4.0% to 4.5% over a month tells you something different than a stable 4.5% for three months.</p>

<h2>3. The Gold-to-Silver Ratio</h2>

<p>We covered this in depth in our <a href="/blog/gold-silver-ratio-explained-investors-2026">dedicated article</a>. The short version: a rising ratio suggests risk aversion (investors prefer gold's safety). A falling ratio suggests risk appetite is expanding (silver's industrial demand benefits from growth).</p>

<p>It's a proxy for the market's growth expectations, viewed through the lens of precious metals.</p>

<h2>4. CNN Fear & Greed Index</h2>

<p>This composite index combines seven market indicators (stock price momentum, stock price strength, stock price breadth, put/call ratio, junk bond demand, market volatility, and safe haven demand) into a single 0-100 score.</p>

<ul>
<li><strong>0-25 (Extreme Fear):</strong> Markets are oversold. Historically a contrarian buy signal.</li>
<li><strong>25-45 (Fear):</strong> Caution prevails. Selective buying opportunities exist.</li>
<li><strong>45-55 (Neutral):</strong> No strong signal. Focus on fundamentals.</li>
<li><strong>55-75 (Greed):</strong> Markets are optimistic. Be cautious about adding risk.</li>
<li><strong>75-100 (Extreme Greed):</strong> Markets are overheated. Warren Buffett's "be fearful when others are greedy" applies here.</li>
</ul>

<h2>5. The DXY (US Dollar Index)</h2>

<p>The DXY measures the dollar against a basket of six major currencies (euro, yen, pound, Canadian dollar, Swiss franc, Swedish krona). A strong dollar typically means:</p>

<ul>
<li>Pressure on gold and commodities (priced in dollars)</li>
<li>Headwinds for US multinationals (overseas earnings worth less)</li>
<li>Stress on emerging markets (their dollar-denominated debt gets more expensive)</li>
<li>Relative advantage for US consumers and importers</li>
</ul>

<p>A weakening dollar is generally bullish for gold, international stocks, and commodities.</p>

<h2>Putting It All Together</h2>

<p>These five indicators (VIX, 10-year yield, gold/silver ratio, Fear & Greed, and DXY) give you a real-time macro snapshot. Check them every morning before you look at your portfolio. They tell you <em>why</em> your portfolio is moving, not just <em>that</em> it's moving.</p>

<p>Nickel & Dime's dashboard shows all five on the pulse bar, with the sentiment gauges and economics tab providing the deeper context. It's designed for exactly this workflow: glance at the macro picture, then look at your portfolio in that context.</p>

<p>The best investors don't react to price movements; they interpret them through the macro lens. These five indicators are your lens.</p>"""
    },
]


def seed():
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        from app.models.blog import BlogPost

        created = 0
        for post_data in POSTS:
            existing = BlogPost.query.filter_by(slug=post_data["slug"]).first()
            if existing:
                print(f"  SKIP (exists): {post_data['slug']}")
                continue

            post = BlogPost(
                slug=post_data["slug"],
                title=post_data["title"],
                excerpt=post_data["excerpt"],
                body=post_data["body"],
                published=True,
                meta_description=post_data["meta_description"],
            )
            db.session.add(post)
            created += 1
            print(f"  CREATE: {post_data['slug']}")

        db.session.commit()
        print(f"\nDone! Created {created} posts, skipped {len(POSTS) - created}.")


if __name__ == "__main__":
    seed()
