import Foundation

/// Adressen jobben hos GitHub publiserer til. Alt appen viser kommer herfra.
enum Tjeneste {
    static let grunnadresse = URL(string: "https://gladesigner.github.io/galleriradar-oslo/")!
    static var data: URL { grunnadresse.appendingPathComponent("data.json") }
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
    let url: String
    let bilde: String?
    let sammendrag: String?
    let type: String?
    let forsteGang: String
    let borte: Bool?

    var id: String { nokkel }

    enum CodingKeys: String, CodingKey {
        case nokkel, galleri, kategori, tittel, kunstnere, periode, url, bilde, sammendrag, type, borte
        case kildeId = "kilde_id"
        case startDato = "start_dato"
        case sluttDato = "slutt_dato"
        case forsteGang = "forste_gang"
    }

    var lenke: URL? { URL(string: url) }

    var bildeadresse: URL? {
        guard let bilde, !bilde.isEmpty else { return nil }
        if bilde.hasPrefix("http") { return URL(string: bilde) }
        return Tjeneste.grunnadresse.appendingPathComponent(bilde)
    }

    var start: Date? { Dato.fra(startDato) }
    var slutt: Date? { Dato.fra(sluttDato) }

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

    enum CodingKeys: String, CodingKey {
        case bygget, antall, kilder, utstillinger
        case iDag = "i_dag"
    }

    static let tom = Datasett(bygget: "", iDag: "", antall: 0, kilder: [], utstillinger: [])
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
