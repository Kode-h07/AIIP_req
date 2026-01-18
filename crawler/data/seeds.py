# crawler/data/seeds.py

SEEDS = [
    # Intergovernmental / IGO
    {
        "source_name": "WIPO",
        "source_type": "intergovernmental",
        "url": "https://www.wipo.int/about-ip/en/artificial_intelligence/",
    },
    {
        "source_name": "OECD",
        "source_type": "intergovernmental",
        "url": "https://www.oecd.org/sti/artificial-intelligence/",
    },
    {
        "source_name": "UNESCO",
        "source_type": "intergovernmental",
        "url": "https://www.unesco.org/en/artificial-intelligence",
    },
    {
        "source_name": "WTO",
        "source_type": "intergovernmental",
        "url": "https://www.wto.org/english/tratop_e/trips_e/trips_e.htm",
    },
    # United States
    {
        "source_name": "US Copyright Office",
        "source_type": "government",
        "url": "https://www.copyright.gov/ai/",
    },
    {
        "source_name": "USPTO",
        "source_type": "government",
        "url": "https://www.uspto.gov/about-us/news-updates",
    },
    {
        "source_name": "NIST",
        "source_type": "government",
        "url": "https://www.nist.gov/itl/ai-risk-management-framework",
    },
    {
        "source_name": "FTC",
        "source_type": "regulator",
        "url": "https://www.ftc.gov/policy",
    },
    {
        "source_name": "U.S. Department of Commerce",
        "source_type": "government",
        "url": "https://www.commerce.gov/news",
    },
    # European Union
    {
        "source_name": "European Commission",
        "source_type": "government",
        "url": "https://commission.europa.eu/law/law-topic/intellectual-property_en",
    },
    {
        "source_name": "EUIPO",
        "source_type": "regulator",
        "url": "https://euipo.europa.eu/ohimportal/en/news",
    },
    {
        "source_name": "EPO",
        "source_type": "regulator",
        "url": "https://www.epo.org/en/news-events",
    },
    {
        "source_name": "EDPB",
        "source_type": "regulator",
        "url": "https://www.edpb.europa.eu/news/news_en",
    },
    # United Kingdom
    {
        "source_name": "UK IPO",
        "source_type": "government",
        "url": "https://www.gov.uk/government/organisations/intellectual-property-office",
    },
    {
        "source_name": "UK DSIT",
        "source_type": "government",
        "url": "https://www.gov.uk/government/organisations/department-for-science-innovation-and-technology",
    },
    {
        "source_name": "UK CMA",
        "source_type": "regulator",
        "url": "https://www.gov.uk/government/organisations/competition-and-markets-authority",
    },
    # Research centers / think tanks (high-signal)
    {
        "source_name": "Stanford HAI",
        "source_type": "research_center",
        "url": "https://hai.stanford.edu/news",
    },
    {
        "source_name": "Brookings",
        "source_type": "think_tank",
        "url": "https://www.brookings.edu/topic/technology-innovation/",
    },
    {
        "source_name": "RAND",
        "source_type": "think_tank",
        "url": "https://www.rand.org/topics/artificial-intelligence.html",
    },
    # Consulting firms (high volume; filter by download links)
    {
        "source_name": "McKinsey",
        "source_type": "consulting_firm",
        "url": "https://www.mckinsey.com/capabilities/quantumblack/our-insights",
    },
    {
        "source_name": "BCG",
        "source_type": "consulting_firm",
        "url": "https://www.bcg.com/publications",
    },
    {
        "source_name": "Deloitte",
        "source_type": "consulting_firm",
        "url": "https://www2.deloitte.com/global/en/insights.html",
    },
    {
        "source_name": "PwC",
        "source_type": "consulting_firm",
        "url": "https://www.pwc.com/gx/en/issues/data-and-analytics.html",
    },
    # Law firms (alerts sometimes include downloadable PDFs)
    {
        "source_name": "Latham & Watkins",
        "source_type": "law_firm",
        "url": "https://www.lw.com/en/insights",
    },
    {
        "source_name": "Clifford Chance",
        "source_type": "law_firm",
        "url": "https://www.cliffordchance.com/insights.html",
    },
    # US Government / Policy (high signal for AI x IP)
    {
        "source_name": "The White House",
        "source_type": "government",
        "url": "https://www.whitehouse.gov/briefing-room/",
    },
    {
        "source_name": "U.S. Congress",
        "source_type": "government",
        "url": "https://www.congress.gov/",
    },
    {
        "source_name": "U.S. Chamber of Commerce",
        "source_type": "other",
        "url": "https://www.uschamber.com/",
    },
    {
        "source_name": "U.S. Department of Commerce",
        "source_type": "government",
        "url": "https://www.commerce.gov/news",
    },
    {
        "source_name": "USPTO",
        "source_type": "government",
        "url": "https://www.uspto.gov/about-us/news-updates",
    },
    {
        "source_name": "USPTO - AI",
        "source_type": "government",
        "url": "https://www.uspto.gov/initiatives/artificial-intelligence",
    },
    # Other patent offices (you mentioned “country patent offices”)
    {
        "source_name": "EPO",
        "source_type": "regulator",
        "url": "https://www.epo.org/en/news-events",
    },
    {
        "source_name": "JPO",
        "source_type": "government",
        "url": "https://www.jpo.go.jp/e/news/index.html",
    },
    {
        "source_name": "KIPO",
        "source_type": "government",
        "url": "https://www.kipo.go.kr/en/MainApp?c=1000",
    },
    {
        "source_name": "IPO India",
        "source_type": "government",
        "url": "https://ipindia.gov.in/news.htm",
    },
    {
        "source_name": "IP Australia",
        "source_type": "government",
        "url": "https://www.ipaustralia.gov.au/about-us/news-and-community/blog",
    },
    {
        "source_name": "CIPO (Canada)",
        "source_type": "government",
        "url": "https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/news",
    },
    {
        "source_name": "WIPO",
        "source_type": "intergovernmental",
        "url": "https://www.wipo.int/about-ip/en/artificial_intelligence/",
    },
    {
        "source_name": "OECD",
        "source_type": "intergovernmental",
        "url": "https://www.oecd.org/sti/artificial-intelligence/",
    },
    # Blogs / analysis you explicitly want
    {
        "source_name": "Patently-O",
        "source_type": "other",
        "url": "https://patentlyo.com/",
    },
    {
        "source_name": "State of AI Report",
        "source_type": "research_center",
        "url": "https://www.stateof.ai/",
    },
]
