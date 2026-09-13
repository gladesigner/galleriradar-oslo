import Foundation
import SwiftUI

/// Holder listen appen viser: henter fra nettet, husker siste svar på disk,
/// og vet hva denne telefonen har sett før.
@MainActor
final class Lager: ObservableObject {
    @Published private(set) var data: Datasett = .tom
    @Published private(set) var laster = false
    @Published private(set) var feil: String?
    @Published var merket: Set<String> = []
    /// Stedene brukeren har huket bort. Tomt betyr at alt er med.
    @Published var avKilder: Set<String> = []

    private let arkiv: URL = {
        let mappe = FileManager.default.urls(for: .applicationSupportDirectory,
                                             in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: mappe, withIntermediateDirectories: true)
        return mappe.appendingPathComponent("data.json")
    }()

    init() {
        merket = Set(UserDefaults.standard.stringArray(forKey: "merket") ?? [])
        avKilder = Set(UserDefaults.standard.stringArray(forKey: "avKilder") ?? [])
        lesFraDisk()
    }

    // MARK: henting

    private func lesFraDisk() {
        guard let raa = try? Data(contentsOf: arkiv),
              let d = try? JSONDecoder().decode(Datasett.self, from: raa) else { return }
        data = d
    }

    func hent(tving: Bool = false) async {
        if laster { return }
        laster = true
        defer { laster = false }
        do {
            var forespørsel = URLRequest(url: Tjeneste.data(friskt: tving))
            forespørsel.cachePolicy = .reloadIgnoringLocalCacheData
            let (raa, svar) = try await URLSession.shared.data(for: forespørsel)
            if let http = svar as? HTTPURLResponse, http.statusCode != 200 {
                throw URLError(.badServerResponse)
            }
            let nytt = try JSONDecoder().decode(Datasett.self, from: raa)
            data = nytt
            feil = nil
            try? raa.write(to: arkiv, options: .atomic)
        } catch {
            // Har vi noe fra før, viser vi heller det enn en tom skjerm.
            feil = data.utstillinger.isEmpty ? "Fikk ikke tak i listen." : nil
        }
    }

    // MARK: hva som regnes som nytt

    /// «Nytt» er utstillinger som nettopp har åpnet: i dag og seks dager
    /// bakover. Det er åpningsdatoen som teller, ikke når innhøsteren først
    /// fikk øye på dem – da betyr fanen det samme for alle som åpner appen.
    static let nyttVindu = 6

    var nyttGrense: String {
        let dato = Calendar.current.date(byAdding: .day, value: -Self.nyttVindu, to: Date()) ?? Date()
        return Dato.tekst(dato)
    }

    func erNy(_ u: Utstilling) -> Bool {
        guard !u.erArrangement, let start = u.startDato else { return false }
        let iDag = data.iDag.isEmpty ? Dato.tekst(Date()) : data.iDag
        return start >= nyttGrense && start <= iDag
    }

    // MARK: «vil se»

    func veksleMerke(_ u: Utstilling) {
        if merket.contains(u.nokkel) { merket.remove(u.nokkel) } else { merket.insert(u.nokkel) }
        UserDefaults.standard.set(Array(merket), forKey: "merket")
    }

    func erMerket(_ u: Utstilling) -> Bool { merket.contains(u.nokkel) }

    // MARK: hvilke steder som skal telle med

    func erPaa(_ kildeId: String) -> Bool { !avKilder.contains(kildeId) }

    func veksleKilde(_ kildeId: String) {
        if avKilder.contains(kildeId) { avKilder.remove(kildeId) } else { avKilder.insert(kildeId) }
        UserDefaults.standard.set(Array(avKilder), forKey: "avKilder")
    }

    func settRegion(_ region: String, pa: Bool) {
        for s in data.stederIRegion(region) {
            if pa { avKilder.remove(s.id) } else { avKilder.insert(s.id) }
        }
        UserDefaults.standard.set(Array(avKilder), forKey: "avKilder")
    }

    func regionErPaa(_ region: String) -> Bool {
        let steder = data.stederIRegion(region)
        return !steder.isEmpty && steder.allSatisfy { erPaa($0.id) }
    }

    // MARK: utvalg

    enum Visning: String, CaseIterable, Identifiable {
        case naa = "Nå", nytt = "Nytt", kommer = "Kommer", fast = "Permanent"
        case arrangement = "Arrangementer", merket = "Min liste"
        var id: String { rawValue }
    }

    func sted(for kildeId: String) -> Sted? { data.kilder.first { $0.id == kildeId } }

    func utstillinger(_ visning: Visning, sok: String = "", sted: String? = nil) -> [Utstilling] {
        let iDag = data.iDag.isEmpty ? Dato.tekst(Date()) : data.iDag
        var liste: [Utstilling]

        // Steder brukeren har huket bort skal ikke dukke opp noe sted.
        let valgte = data.utstillinger.filter { erPaa($0.kildeId) }
        // Utstillingsfanene viser bare utstillinger; arrangementene har sin egen.
        let utstillinger = valgte.filter { !$0.erArrangement }

        switch visning {
        case .naa:
            // Har åpnet og ikke stengt. En utstilling som mangler sluttdato,
            // men har åpnet, går fortsatt – den er ikke permanent.
            liste = utstillinger.filter { u in
                (u.borte ?? false) == false
                    && (u.startDato != nil || u.sluttDato != nil)
                    && (u.sluttDato == nil || u.sluttDato! >= iDag)
                    && (u.startDato == nil || u.startDato! <= iDag)
            }
            liste.sort { ($0.sluttDato ?? "9999") < ($1.sluttDato ?? "9999") }
        case .fast:
            // Permanent er de som ikke har datoer i det hele tatt.
            liste = utstillinger.filter {
                ($0.borte ?? false) == false && $0.startDato == nil && $0.sluttDato == nil
            }
            liste.sort { $0.galleri.localizedCaseInsensitiveCompare($1.galleri) == .orderedAscending }
        case .kommer:
            liste = utstillinger.filter { ($0.startDato ?? "") > iDag }
            liste.sort { ($0.startDato ?? "") < ($1.startDato ?? "") }
        case .arrangement:
            // Kommende måned, det som skjer først øverst.
            let om_en_maaned = Dato.tekst(
                Calendar.current.date(byAdding: .day, value: 31, to: Date()) ?? Date())
            liste = valgte.filter {
                $0.erArrangement && ($0.startDato ?? "") >= iDag && ($0.startDato ?? "") <= om_en_maaned
            }
            // Samme dag avgjør klokkeslettet; det som mangler tid stilles sist.
            liste.sort {
                ($0.startDato ?? "", $0.fraTid ?? "99:99")
                    < ($1.startDato ?? "", $1.fraTid ?? "99:99")
            }
        case .nytt:
            // nettopp åpnet, og fortsatt oppe
            liste = utstillinger.filter { erNy($0) && ($0.sluttDato == nil || $0.sluttDato! >= iDag) }
            liste.sort { ($1.startDato ?? "") < ($0.startDato ?? "") }
        case .merket:
            liste = data.utstillinger.filter { merket.contains($0.nokkel) }   // merkede vises alltid
            liste.sort { ($0.sluttDato ?? "9999") < ($1.sluttDato ?? "9999") }
        }

        if let sted, !sted.isEmpty {
            liste = liste.filter { $0.kildeId == sted }
        }
        let q = sok.trimmingCharacters(in: .whitespaces).lowercased()
        if !q.isEmpty {
            liste = liste.filter {
                "\($0.tittel) \($0.kunstnere ?? "") \($0.galleri) \($0.sammendrag ?? "")"
                    .lowercased().contains(q)
            }
        }
        return liste
    }

    func antall(_ visning: Visning) -> Int { utstillinger(visning).count }

    /// Alt et sted har på plakaten nå: utstillinger først, så arrangementer.
    func paaSted(_ kildeId: String) -> (utstillinger: [Utstilling], arrangementer: [Utstilling]) {
        (utstillinger(.naa, sted: kildeId) + utstillinger(.fast, sted: kildeId),
         utstillinger(.arrangement, sted: kildeId))
    }

    /// Stedene som har noe å vise – grunnlaget for kartet. Tallet på nåla er
    /// summen av det listen under viser, ikke bare utstillingene.
    func stederMedProgram() -> [(sted: Sted, antall: Int)] {
        data.kilder
            .filter { $0.harPosisjon && erPaa($0.id) }
            .compactMap { s in
                let p = paaSted(s.id)
                let n = p.utstillinger.count + p.arrangementer.count
                return n == 0 ? nil : (s, n)
            }
    }
}
