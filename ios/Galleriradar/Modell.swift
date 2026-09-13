import Foundation

/// Adressen jobben hos GitHub publiserer til. Alt appen viser kommer herfra.
enum Tjeneste {
    static let grunnadresse = URL(string: "https://gladesigner.github.io/galleriradar-oslo/")!

    /// GitHub Pages ber nettleseren ta vare på filene en stund. Uten et
    /// tidsstempel i adressen kan appen bli sittende med gårsdagens liste.
    static func data(friskt: Bool = false) -> URL {
        let fil = grunnadresse.appendingPathComponent("data.json")
        guard var deler = URLComponents(url: fil, resolvingAgainstBaseURL: false) else { return fil }
        let bolk = friskt ? Int(Date().timeIntervalSince1970)
                          : Int(Date().timeIntervalSince1970 / 300) * 300
        deler.queryItems = [URLQueryItem(name: "t", value: String(bolk))]
        return deler.url ?? fil
    }
}

struct Utstilling: Codable, Identifiable, Hashable {
    let nokkel: String
    let kildeId: String
    let galleri: String
    let kategori: String?
    let tittel: String
    let kunstnere: String?
    let periode: String?
    let startDato: String?
    let sluttDato: String?
    let fraTid: String?
    let tilTid: String?
    let url: String
    let bilde: String?
    let sammendrag: String?
    let type: String?
    let forsteGang: String
    let borte: Bool?
    let arrangement: Bool?

    var id: String { nokkel }

    enum CodingKeys: String, CodingKey {
        case nokkel, galleri, kategori, tittel, kunstnere, periode, url, bilde
        case sammendrag, type, borte, arrangement
        case kildeId = "kilde_id"
        case startDato = "start_dato"
        case sluttDato = "slutt_dato"
        case fraTid = "fra_tid"
        case tilTid = "til_tid"
        case forsteGang = "forste_gang"
    }

    /// Enkeltarrangementer – omvisninger, samtaler, konserter – skjer på et
    /// klokkeslett og hører ikke hjemme blant utstillingene.
    var erArrangement: Bool { arrangement ?? false }

    var lenke: URL? { URL(string: url) }

    var bildeadresse: URL? {
        guard let bilde, !bilde.isEmpty else { return nil }
        if bilde.hasPrefix("http") { return URL(string: bilde) }
        return Tjeneste.grunnadresse.appendingPathComponent(bilde)
    }

    var start: Date? { Dato.fra(startDato) }
    var slutt: Date? { Dato.fra(sluttDato) }

    /// Starttidspunktet med klokkeslett, når kilden oppgir et. Brukes til
    /// kalenderforslaget – et arrangement kl. 13 skal ikke bli en heldagspost.
    var starttidspunkt: Date? { Dato.medKlokke(startDato, fraTid) }
    var slutttidspunkt: Date? { Dato.medKlokke(startDato, tilTid) }
    var harKlokkeslett: Bool { starttidspunkt != nil }

    /// Antall dager til siste dag. Nil når utstillingen ikke har sluttdato.
    func dagerIgjen(fra i_dag: Date = Date()) -> Int? {
        guard let slutt else { return nil }
        let dager = Calendar.current.dateComponents([.day],
                                                    from: Calendar.current.startOfDay(for: i_dag),
                                                    to: slutt).day
        guard let dager, dager >= 0 else { return nil }
        return dager
    }

    var undertittel: String {
        let deler = [kunstnere, periode].compactMap { $0 }.filter { !$0.isEmpty }
        return deler.joined(separator: " · ")
    }
}

struct Sted: Codable, Identifiable, Hashable {
    let id: String
    let navn: String
    let url: String
    let kategori: String?
    let region: String?
    let bydel: String?
    let adresse: String?
    let lat: Double?
    let lon: Double?
    let antall: Int
    let feil: String?

    var harPosisjon: Bool { lat != nil && lon != nil }
}

struct Datasett: Codable {
    let bygget: String
    let iDag: String
    let antall: Int
    let kilder: [Sted]
    let utstillinger: [Utstilling]
    let regioner: [String: String]?

    enum CodingKeys: String, CodingKey {
        case bygget, antall, kilder, utstillinger, regioner
        case iDag = "i_dag"
    }

    static let tom = Datasett(bygget: "", iDag: "", antall: 0, kilder: [],
                              utstillinger: [], regioner: nil)

    /// Regionene i rekkefølgen de skal stå i en liste – sørfra og nordover.
    static let regionrekke = ["oslo", "sorlandet", "vestlandet", "midt",
                              "nordland", "troms", "finnmark"]

    func regionNavn(_ id: String) -> String { regioner?[id] ?? id }

    func stederIRegion(_ id: String) -> [Sted] {
        kilder.filter { ($0.region ?? "oslo") == id }
            .sorted { $0.navn.localizedCaseInsensitiveCompare($1.navn) == .orderedAscending }
    }
}

/// Datoene i data.json er rene ISO-datoer uten tidssone.
enum Dato {
    private static let format: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "nb_NO")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    static func fra(_ tekst: String?) -> Date? {
        guard let tekst, !tekst.isEmpty else { return nil }
        return format.date(from: String(tekst.prefix(10)))
    }

    static func tekst(_ dato: Date) -> String { format.string(from: dato) }

    /// «2026-09-13» + «13:00» → tidspunktet på den dagen.
    static func medKlokke(_ dag: String?, _ klokke: String?) -> Date? {
        guard let dag = fra(dag), let klokke, klokke.count == 5 else { return nil }
        let deler = klokke.split(separator: ":").compactMap { Int($0) }
        guard deler.count == 2 else { return nil }
        return Calendar.current.date(bySettingHour: deler[0], minute: deler[1],
                                     second: 0, of: dag)
    }

    /// «2026-09-12T18:25:45» → «12. september kl. 18.25»
    static func lesbart(_ tidspunkt: String) -> String {
        let inn = DateFormatter()
        inn.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        inn.locale = Locale(identifier: "nb_NO")
        guard let d = inn.date(from: tidspunkt) else { return tidspunkt }
        let ut = DateFormatter()
        ut.locale = Locale(identifier: "nb_NO")
        ut.dateFormat = "d. MMMM 'kl.' HH.mm"
        return ut.string(from: d)
    }
}
