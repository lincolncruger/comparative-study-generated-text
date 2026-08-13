import json

new_entries = [
{"ticker":"AAON","fiscal_yearquarter":"2017q3","bullets":[
 "EPS: $0.26 (analyst estimate: $0.29), down 3.7% year-over-year, missing by $0.03",
 "Net sales declined to $101.3 million",
 "Backlog grew 20% to $83.5 million, driven by a strong incoming order rate",
 "Management expects revenue growth to improve once the manufacturing supervisory personnel transition is completed",
 "Gross profit declined to $31.7 million due to higher raw material prices",
 "SG&A rose to $12.0 million due to unusually high warranty expenses, expected to normalize after policy changes",
 "Balance sheet: debt-free, current ratio of 2.9:1, $51.8 million in cash and short-term investments"
]},
{"ticker":"AAON","fiscal_yearquarter":"2018q4","bullets":[
 "Backlog grew 71.8% to $126.8 million at September 30, 2018, attributed to innovative product lines and a positive response to a new R&D lab facility",
 "Net sales: $112.9 million, down 0.6% year-over-year",
 "Diluted EPS: $0.27, down 3.6% year-over-year",
 "Gross profit margin improved sequentially to 29.0% of sales (from 25.2% in Q2 2018), as price increases became effective",
 "Raw material costs remained under pressure due to tariffs",
 "Effective tax rate decreased to 28.2% from 35.3% due to the Tax Cuts and Jobs Act, with an estimated annual rate of ~26%"
]},
{"ticker":"AAON","fiscal_yearquarter":"2019q2","bullets":[
 "Net sales: $113.8 million, +14.9%",
 "Diluted EPS: $0.21, +162.5% from $0.08 prior year",
 "Gross profit: +67.6% to $25.8 million; margin expanded to 22.7% from 15.5%, attributed to 2018 price increases, productivity gains, and higher sales volumes",
 "SG&A expenses fell as a percentage of sales, to 9.7% from 10.3%",
 "Income from operations: +180.2% to $14.5 million",
 "Backlog: +9.7% sequentially and +125% year-over-year to $166.6 million",
 "New 5% price increase announced for early June",
 "Balance sheet: debt-free, current ratio of 3.3:1"
]},
{"ticker":"AAON","fiscal_yearquarter":"2019q4","bullets":[
 "Gross profit: -16.4% to $27.4 million (24.1% of sales, down from 29%), attributed to machine downtime that reduced sheet metal production and unit efficiency",
 "Net sales: +0.5% to $113.5 million",
 "Diluted EPS: -3.7% to $0.26",
 "Management: net sales constrained by sheet metal production capacity; additional fabrication machines coming online to address it",
 "Orders slowed slightly due to extended lead times, which the company is working to reduce",
 "Year-to-date net sales: +7.8% to $346.8 million; year-to-date diluted EPS: +26.3% to $0.72",
 "Backlog: +30.4% year-over-year to $165.3 million"
]},
{"ticker":"AAON","fiscal_yearquarter":"2020q1","bullets":[
 "Q4 diluted EPS: $0.33, +32%",
 "Q4 net sales: $122.6 million, +9.1%",
 "Gross profit: +30.7% to $36.4 million; margin expanded to 29.7% from 24.8%",
 "Full-year diluted EPS: $1.02 on net sales of $469.3 million",
 "Management attributed the improvement to investments in new manufacturing equipment and operational reorganizations",
 "2020 capital expenditure budget: $73.2 million",
 "Cash and cash equivalents: $26.8 million"
]},
{"ticker":"AAON","fiscal_yearquarter":"2020q2","bullets":[
 "Company operated as an essential manufacturer during COVID-19, including supplying units for temporary hospitals in the New York area",
 "Net sales: $137.5 million, +20.8%",
 "Net income: $21.9 million, +149.5%",
 "Diluted EPS: $0.41, +141.2%",
 "Gross profit margin improved to 31.2% of sales, attributed to increased production, fixed-cost absorption, and decreasing raw material costs",
 "Order intake at 92% of expected levels; current ratio of 3.1:1; cash of $35.7 million",
 "Water-source heat pump business had \"growing pains\" in Q1; April bookings strengthening",
 "2020 capital expenditures projected at approximately $73.2 million"
]},
{"ticker":"AAON","fiscal_yearquarter":"2021q4","bullets":[
 "Net sales: $138.6 million",
 "Diluted EPS: $0.29",
 "Gross profit: -11.8% to $36 million; margin contracted to 26.0%",
 "Management described the top line as \"softer than expected\" and margins as \"weaker-than-expected,\" citing labor shortages, supply chain constraints, and raw material inflation",
 "Backlog: record $181.8 million, +114% year-over-year and +32% sequentially",
 "New bookings: +~60%",
 "Management characterized the price/cost pressure as a \"timing factor\" expected to dissipate; 18% total price increases planned for the year, with 5% realized in Q3",
 "Labor shortage progress expected in Q4, though management acknowledged it could linger into 2022"
]},
{"ticker":"AAON","fiscal_yearquarter":"2022q3","bullets":[
 "Diluted EPS: -21.1% to $0.30 from $0.38, primarily due to gross profit margin compression from higher material, component, labor, and freight costs",
 "Net sales: record +45.1% to $208.8 million, including $24.6 million from the BasX acquisition and 10.3% organic volume growth",
 "Backlog: record +235.9% year-over-year to $464.0 million, with an improving margin profile from recent price increases",
 "Management noted BasX revenue synergies materialized faster than expected, and the BasX backlog nearly tripled"
]},
{"ticker":"AAON","fiscal_yearquarter":"2023q1","bullets":[
 "Q4 net sales: record $254.6 million, +86.8%",
 "Diluted EPS: $0.71, +545.5% year-over-year",
 "Gross profit margin improved to 30.8%, the highest since Q1 2020, attributed to price increases and production efficiency gains",
 "Backlog: record $548.0 million, +110.6% year-over-year, with an improved margin profile",
 "Management expects another record year in 2023, supported by strong anticipated cash flow from operations"
]},
{"ticker":"AAON","fiscal_yearquarter":"2024q1","bullets":[
 "Q4 net sales: record $306.6 million, +20.4%",
 "Diluted EPS: $0.56, +19.1%",
 "Gross profit margin expanded to 36.4%",
 "Management expressed cautious optimism for 2024, citing signs of slowing nonresidential construction activity and uncertainty from the refrigerant transition, expecting slower sales and earnings growth than in recent years",
 "Backlog: $510.0 million, up sequentially but down 6.9% year-over-year",
 "Management cited continued market share gains and productivity enhancement opportunities",
 "CFO indicated another year of elevated capital expenditures in 2024"
]},
{"ticker":"AAON","fiscal_yearquarter":"2024q4","bullets":[
 "Net sales: record $327.3 million, +4.9%, driven by the BASX segment (+58.8%) and AAON Coil Products segment (+36.7%) on data center demand",
 "Diluted EPS: $0.63, approximately flat year-over-year",
 "Gross profit margin contracted to 34.9%",
 "Backlog: $647.7 million, +32.0% year-over-year, majority consisting of data center equipment orders for 2025",
 "New orders: ~$174.5 million for a liquid cooling solution for a data center customer, expected to be produced and shipped in H1 2025",
 "Capacity expansion: new 787,000 square foot facility planned to accommodate data center demand",
 "Average 12-month analyst price target rose 14.67%"
]},
]

with open("data/bullets_241.json") as f:
    existing = {(e["ticker"], e["fiscal_yearquarter"]): e["bullets"] for e in json.load(f)}

for e in new_entries:
    existing[(e["ticker"], e["fiscal_yearquarter"])] = e["bullets"]

out = [{"ticker": t, "fiscal_yearquarter": q, "bullets": b} for (t, q), b in existing.items()]
with open("data/bullets_241.json", "w") as f:
    json.dump(out, f, indent=2)

print("Total entries now:", len(out))
print("Rows updated this batch:", len(new_entries))
