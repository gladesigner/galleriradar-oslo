import BackgroundTasks
import Foundation
import UserNotifications

/// Varsler uten varseltjener: appen ser etter nye utstillinger i bakgrunnen og
/// gir beskjed selv. iOS bestemmer når den får lov, typisk et par ganger om dagen.
enum Varsler {
    static let oppgaveId = "no.gladesigner.galleriradar.hent"
    private static let settNokler = "setteNokler"

    static func tidspunkt(_ iso: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        f.locale = Locale(identifier: "nb_NO")
        return f.date(from: iso)
    }

    // MARK: tillatelse

    static func spørOmLov() async -> Bool {
        let senter = UNUserNotificationCenter.current()
        let nå = await senter.notificationSettings()
        if nå.authorizationStatus == .notDetermined {
            return (try? await senter.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        }
        return nå.authorizationStatus == .authorized
    }

    static var påskrudd: Bool {
        get { UserDefaults.standard.object(forKey: "varsling") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "varsling") }
    }

    // MARK: bakgrunnsjobben

    static func registrer() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: oppgaveId, using: nil) { oppgave in
            guard let oppgave = oppgave as? BGAppRefreshTask else { return }
            planlegg()
            let arbeid = Task {
                let nye = await seEtterNytt()
                if nye > 0 { await meld(nye) }
                oppgave.setTaskCompleted(success: true)
            }
            oppgave.expirationHandler = { arbeid.cancel() }
        }
    }

    static func planlegg() {
        let b = BGAppRefreshTaskRequest(identifier: oppgaveId)
        b.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 3600)
        try? BGTaskScheduler.shared.submit(b)
    }

    /// Henter listen og teller hvor mye som ikke var der sist. Brukes både av
    /// bakgrunnsjobben og når appen åpnes.
    static func seEtterNytt() async -> Int {
        guard påskrudd else { return 0 }
        guard let (raa, _) = try? await URLSession.shared.data(from: Tjeneste.data(friskt: true)),
              let d = try? JSONDecoder().decode(Datasett.self, from: raa) else { return 0 }

        let iDag = d.iDag
        let gjeldende = d.utstillinger.filter { $0.sluttDato == nil || $0.sluttDato! >= iDag }
        let nøkler = Set(gjeldende.map(\.nokkel))
        let kjente = Set(UserDefaults.standard.stringArray(forKey: settNokler) ?? [])

        UserDefaults.standard.set(Array(nøkler), forKey: settNokler)
        if kjente.isEmpty { return 0 }          // første gang: ingenting er «nytt»

        let nye = gjeldende.filter { !kjente.contains($0.nokkel) }
        if nye.isEmpty { return 0 }
        UserDefaults.standard.set(nye.map(\.nokkel), forKey: "sisteNye")
        return nye.count
    }

    static func meld(_ antall: Int) async {
        guard await spørOmLov() else { return }
        let innhold = UNMutableNotificationContent()
        innhold.title = antall == 1 ? "Ny utstilling i Oslo" : "\(antall) nye utstillinger i Oslo"
        innhold.body = "Åpne Galleriradar for å se hva som har dukket opp."
        innhold.sound = .default
        innhold.badge = NSNumber(value: antall)
        let be = UNNotificationRequest(identifier: UUID().uuidString, content: innhold, trigger: nil)
        try? await UNUserNotificationCenter.current().add(be)
    }
}
