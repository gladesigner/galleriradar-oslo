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

    private let arkiv: URL = {
        let mappe = FileManager.default.urls(for: .applicationSupportDirectory,
                                             in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: mappe, withIntermediateDirectories: true)
        return mappe.appendingPathComponent("data.json")
    }()

    init() {
        merket = Set(UserDefaults.standard.stringArray(forKey: "merket") ?? [])
        // Første gang appen åpnes regnes alt som sett – ellers ville hele
        // listen ha lyst opp som ny.
        if UserDefaults.standard.double(forKey: "sistSett") == 0 {
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: "sistSett")
        }
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

    // MARK: hva denne telefonen har sett

    /// Settes første gang appen åpnes, så ikke hele basen lyser opp som ny.
    var sistSett: Date {
        get {
            let t = UserDefaults.standard.double(forKey: "sistSett")
            return t > 0 ? Date(timeIntervalSince1970: t) : .distantPast
        }
        set { UserDefaults.standard.set(newValue.timeIntervalSince1970, forKey: "sistSett") }
    }

    func merkAltSomSett() {
        sistSett = Date()
        objectWillChange.send()
    }

    func erNy(_ u: Utstilling) -> Bool {
        guard let sett = Varsler.tidspunkt(u.forsteGang) else { return false }
        return sett > sistSett
    }

    // MARK: «vil se»

    func veksleMerke(_ u: Utstilling) {
        if merket.contains(u.nokkel) { merket.remove(u.nokkel) } else { merket.insert(u.nokkel) }
        UserDefaults.standard.set(Array(merket), forKey: "merket")
    }

    func erMerket(_ u: Utstilling) -> Bool { merket.contains(u.nokkel) }

    // MARK: utvalg

    enum Visning: String, CaseIterable, Identifiable {
        case naa = "Nå", nytt = "Nytt", kommer = "Kommer", merket = "Vil se"
        var id: String { rawValue }
    }

    func sted(for kildeId: String) -> Sted? { data.kilder.first { $0.id == kildeId } }

    func utstillinger(_ visning: Visning, sok: String = "", sted: String? = nil) -> [Utstilling] {
        let iDag = data.iDag.isEmpty ? Dato.tekst(Date()) : data.iDag
        var liste: [Utstilling]

        switch visning {
        case .naa:
            liste = data.utstillinger.filter { u in
                (u.borte ?? false) == false
                    && (u.sluttDato == nil || u.sluttDato! >= iDag)
                    && (u.startDato == nil || u.startDato! <= iDag)
            }
            liste.sort { ($0.sluttDato ?? "9999") < ($1.sluttDato ?? "9999") }
        case .kommer:
            liste = data.utstillinger.filter { ($0.startDato ?? "") > iDag }
            liste.sort { ($0.startDato ?? "") < ($1.startDato ?? "") }
        case .nytt:
            liste = data.utstillinger.filter { erNy($0) && ($0.sluttDato == nil || $0.sluttDato! >= iDag) }
            liste.sort { $0.forsteGang > $1.forsteGang }
        case .merket:
            liste = data.utstillinger.filter { merket.contains($0.nokkel) }
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

    /// Stedene som har noe å vise akkurat nå – grunnlaget for kartet.
    func stederMedProgram() -> [(sted: Sted, utstillinger: [Utstilling])] {
        let naa = utstillinger(.naa)
        return data.kilder
            .filter { $0.harPosisjon }
            .compactMap { s in
                let mine = naa.filter { $0.kildeId == s.id }
                return mine.isEmpty ? nil : (s, mine)
            }
    }
}
