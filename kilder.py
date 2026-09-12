"""Kildene appen høster fra – ett oppslag per visningssted.

Hver kilde er en ordbok. Feltene som betyr noe:
    id            – stabil nøkkel, brukes i basen
    navn          – slik galleriet skal hete i appen
    kategori      – museum | kunsthall | galleri | kunstnerdrevet
    url           – nettstedets forside (vises i appen)
    sider         – oversiktssidene som skal hentes (uten: bruker url)
    element       – CSS-velger som rammer inn én utstilling
    tittel/dato/kunstnere/bilde/sammendrag/merkelapp – CSS-velgere i elementet
                    (flere alternativer skilles med |)
    hopp_over     – titler som ikke er utstillinger (regex)

Nye gallerier legges til ved å skrive en ny ordbok her. Test med:
    .venv/bin/python hent.py <id>
"""

SAFARI = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                         "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")}

KILDER: list[dict] = [
    # ───────────────────────── museer ─────────────────────────
    {
        "id": "nasjonalmuseet", "navn": "Nasjonalmuseet", "kategori": "museum",
        "url": "https://www.nasjonalmuseet.no/", "bydel": "Vika",
        "type_adapter": "funk", "funksjon": "nasjonalmuseet",
        "detalj_dato": ".event-metadata__text-and-icon span.block|.event-metadata__text-and-icon",
    },
    {
        "id": "munch", "navn": "MUNCH", "kategori": "museum", "bydel": "Bjørvika",
        "url": "https://www.munch.no/", "sider": ["https://www.munch.no/utstillinger"],
        "hoder": SAFARI,
        "element": ".ExhibitionCard",
        "tittel": ".ExhibitionCard__subtitle|.ExhibitionCard__title",
        "kunstnere": ".ExhibitionCard__title",
        "dato": ".ExhibitionCard__intro span|.ExhibitionCard__intro",
        "url_monster": r"/utstillinger/",
        "reserve": True,          # munch.no stenger ute datasentre
    },
    {
        "id": "afmuseet", "navn": "Astrup Fearnley Museet", "kategori": "museum",
        "bydel": "Tjuvholmen", "url": "https://www.afmuseet.no/",
        "sider": ["https://www.afmuseet.no/utstillinger/", "https://www.afmuseet.no/arrangementer/"],
        "element": ".t2-featured-single-post",
        "tittel": ".wp-block-t2-post-title",
        "dato": ".wp-block-afm-block-post-dates",
        "merkelapp": ".wp-block-afm-block-post-type",
        "sammendrag": ".t2-post-excerpt",
    },
    {
        "id": "hok", "navn": "Henie Onstad Kunstsenter", "kategori": "museum",
        "bydel": "Høvikodden", "url": "https://www.hok.no/",
        "sider": ["https://www.hok.no/utstillinger"],
        "element": "article.grid-item",
        "tittel": "h3|h2",
        "kunstnere": "h2",
        "dato": ".f-sm|time|.date",
        "url_monster": r"/utstillinger/",
    },
    {
        "id": "vigeland", "navn": "Vigeland-museet", "kategori": "museum",
        "bydel": "Frogner", "url": "https://vigeland.museum.no/",
        "element": "a[href*='/utstillinger/']", "lenke": "self",
        "tittel": "self",
        "dato": ".f-sm|time|.date",
        "url_monster": r"/utstillinger/[^/]+$",
        "detalj": True, "tittel_fra_detalj": True, "krev_dato": True,
    },

    # ─────────────────────── kunsthaller ───────────────────────
    {
        "id": "kunstnerneshus", "navn": "Kunstnernes Hus", "kategori": "kunsthall",
        "bydel": "St. Hanshaugen", "url": "https://kunstnerneshus.no/",
        "sider": ["https://kunstnerneshus.no/program"],
        "element": "article.LinkItem",
        "tittel": "h1",
        "kunstnere": ".LinkItem__head__sub",
        "dato": ".LinkItem__head__sub",
        "merkelapp": ".LinkItem__head__categories",
    },
    {
        "id": "kunsthalloslo", "navn": "Kunsthall Oslo", "kategori": "kunsthall",
        "bydel": "Bjørvika", "url": "https://kunsthalloslo.no/",
        "sider": ["https://kunsthalloslo.no/?lang=nb"],
        "element": "li.wp-block-post",
        "tittel": ".wp-block-post-title",
        "dato": ".wp-block-post-excerpt|.wp-block-post-date|time",
        "sammendrag": ".wp-block-post-excerpt",
    },
    {
        "id": "uks", "navn": "UKS – Unge Kunstneres Samfund", "kategori": "kunsthall",
        "bydel": "Grønland", "url": "https://www.uks.no/",
        "element": "section.section__hero .row",
        "tittel": ".column__title",
        "dato": ".column__date|.column--two|.column",
        "kunstnere": ".column__artists|.column__subtitle",
    },
    {
        "id": "oslokunstforening", "navn": "Oslo Kunstforening", "kategori": "kunsthall",
        "bydel": "Kvadraturen", "url": "https://www.oslokunstforening.no/",
        "element": "li.archive__item",
        "tittel": ".archive__item__title em|.archive__item__title",
        "kunstnere": ".archive__item__title",
        "dato": ".small",
        "ar_hint": {"foreldre": ".rows", "velger": ""},
        "url_monster": r"/utstillinger/",
        "maks": 80,
    },
    {
        "id": "fotogalleriet", "navn": "Fotogalleriet", "kategori": "kunsthall",
        "bydel": "Sentrum", "url": "https://fotogalleriet.no/",
        "element": "li.grid-item.exhibition, li.grid-item.event",
        "tittel": ".content-title",
        "kunstnere": ".content-inner--title .content-subtitle",
        "dato": ".exhibition-dates|.content-date",
        "merkelapp": ".content-inner--info .content-subtitle",
    },
    {
        "id": "kunstnerforbundet", "navn": "Kunstnerforbundet", "kategori": "kunsthall",
        "bydel": "Kvadraturen", "url": "https://kunstnerforbundet.no/",
        "sider": ["https://kunstnerforbundet.no/utstillinger"],
        "element": ".periods article",
        "underelement": ".exhibition",
        "tittel": "a",
        "dato": ".period",
        "url_monster": r"/utstillinger/",
        "detalj": True, "maks": 60,
    },

    # ──────────────── kommersielle gallerier ────────────────
    {
        "id": "standardoslo", "navn": "STANDARD (OSLO)", "kategori": "galleri",
        "bydel": "Bislett", "url": "https://www.standardoslo.no/",
        "sider": ["https://www.standardoslo.no/exhibitions"],
        "element": "ul.clearwithin > li",
        "tittel": ".title|h2|h3",
        "dato": ".date|.dates|.caption",
        "url_monster": r"/exhibitions/",
        "krev_dato": True,
    },
    {
        "id": "oslcontemporary", "navn": "OSL contemporary", "kategori": "galleri",
        "bydel": "Skøyen", "url": "https://oslcontemporary.com/",
        "sider": ["https://oslcontemporary.com/exhibitions"],
        "element": ".opener-preview",
        "tittel": ".inner-col p|h3",
        "kunstnere": "h3",
        "dato": "p.label",
        "ar_hint": {"foreldre": "section.waypoint", "velger": "h2|h3|.year"},
        "url_monster": r"/exhibitions/",
        "krev_dato": True,
    },
    {
        "id": "galleririis", "navn": "Galleri Riis", "kategori": "galleri",
        "bydel": "Frogner", "url": "https://galleririis.com/",
        "sider": ["https://galleririis.com/exhibitions"],
        "element": "a.exhibition", "lenke": "self",
        "tittel": ".exhibition-name",
        "kunstnere": ".exhibition-artists",
        "dato": ".info div",
        "krev_dato": True, "maks": 40,
    },
    {
        "id": "semmingsen", "navn": "Galleri Semmingsen", "kategori": "galleri",
        "bydel": "Frogner", "url": "https://semmingsen.no/",
        "element": ".ue-grid-item",
        "tittel": ".ue-grid-item-title",
        "dato": ".ue-grid-item-title",
        "krev_dato": True, "maks": 20,
    },
    {
        "id": "format", "navn": "Galleri Format", "kategori": "galleri",
        "bydel": "Sentrum", "url": "https://www.format.no/",
        "sider": ["https://www.format.no/exhibitions-1", "https://www.format.no/upcoming"],
        "element": ".sqs-block.image-block",
        "tittel": "self",
        "dato": ".image-subtitle|p|self",
        "krev_dato": True, "maks": 30,
    },

    # ──────────────── kunstnerdrevne og andre ────────────────
    {
        "id": "femtensesse", "navn": "FEMTENSESSE", "kategori": "kunstnerdrevet",
        "bydel": "Ryen", "url": "https://femtensesse.no/",
        "element": "article.query-item.item-s-12",
        "tittel": "h2|h3|.query-item-title",
        "kunstnere": "h3|.query-item-subtitle",
        "dato": ".query-item-date|p|div",
        "url_monster": r"femtensesse\.no/(project|exhibition)",
        "krev_dato": True, "maks": 30,
    },
    {
        "id": "ateliernord", "navn": "Atelier Nord", "kategori": "kunstnerdrevet",
        "bydel": "Grünerløkka", "url": "https://ateliernord.no/",
        "element": "article, .main-project-title-container",
        "tittel": "h2.entry-title|h2|h3",
        "dato": "time|.date",
        "url_monster": r"ateliernord\.no/(?!$|\?|#)[a-z0-9-]{4,}",
        "detalj": True, "krev_dato": True, "maks": 20,
    },
    {
        "id": "norskegrafikere", "navn": "Norske Grafikere", "kategori": "galleri",
        "bydel": "Sentrum", "url": "https://norske-grafikere.no/",
        "sider": ["https://norske-grafikere.no/utstillinger/",
                  "https://norske-grafikere.no/tidligere-utstillinger/"],
        "element": "figcaption.rollover-content",
        "tittel": ".entry-title",
        "dato": "p",
        "sammendrag": "p:nth-of-type(2)",
        "krev_dato": True, "maks": 40,
    },
    {
        "id": "lnm", "navn": "Galleri LNM", "kategori": "galleri",
        "bydel": "Sentrum", "url": "https://lnm.no/",
        "sider": ["https://lnm.no/utstillinger"],
        "element": "div.col.three",
        "tittel": "h3",
        "kunstnere": "h2",
        "dato": "figcaption .body-size",
        "url_monster": r"/utstillinger/",
        "maks": 60,
    },
]

KILDE_ETTER_ID = {k["id"]: k for k in KILDER}
