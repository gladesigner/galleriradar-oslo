import EventKit
import EventKitUI
import MapKit
import SwiftUI

// MARK: - farger

extension Color {
    static let papir = Color(light: #colorLiteral(red: 0.965, green: 0.957, blue: 0.941, alpha: 1),
                             dark: #colorLiteral(red: 0.075, green: 0.071, blue: 0.063, alpha: 1))
    static let aksent = Color(light: #colorLiteral(red: 0.604, green: 0.231, blue: 0.133, alpha: 1),
                              dark: #colorLiteral(red: 0.878, green: 0.541, blue: 0.416, alpha: 1))
}

extension Color {
    init(light: UIColor, dark: UIColor) {
        self.init(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}

// MARK: - hovedvisning

struct Hovedvisning: View {
    @EnvironmentObject private var lager: Lager
    @State private var fane = 0
    /// Byttes ut hver gang man trykker på utstillingsfanen, slik at listen
    /// bygges opp på nytt: tilbake til Nå, tomt søk og øverst på siden.
    @State private var listenokkel = UUID()

    private var valgtFane: Binding<Int> {
        Binding(get: { fane }, set: { ny in
            if ny == 0 { listenokkel = UUID() }
            fane = ny
        })
    }

    var body: some View {
        TabView(selection: valgtFane) {
            ListeVisning()
                .id(listenokkel)
                .tag(0)
                .tabItem { Label("Utstillinger", systemImage: "square.grid.2x2") }
                .badge(lager.antall(.nytt))

            ListeVisning(fast: .arrangement)
                .tag(1)
                .tabItem { Label("Arrangement", systemImage: "calendar") }

            KartVisning()
                .tag(2)
                .tabItem { Label("Kart", systemImage: "map") }

            ListeVisning(fast: .merket)
                .tag(3)
                .tabItem { Label("Min liste", systemImage: "star") }

            OmVisning()
                .tag(4)
                .tabItem { Label("Om", systemImage: "info.circle") }
        }
        .tint(.aksent)
    }
}

// MARK: - listen

struct ListeVisning: View {
    var fast: Lager.Visning?
    @EnvironmentObject private var lager: Lager
    @State private var visning: Lager.Visning = .naa
    @State private var sok = ""

    private var valgt: Lager.Visning { fast ?? visning }

    var body: some View {
        NavigationStack {
            Group {
                let liste = lager.utstillinger(valgt, sok: sok)
                if liste.isEmpty {
                    Tomtrom(visning: valgt, laster: lager.laster)
                } else {
                    List {
                        if valgt == .nytt {
                            Text("Åpnet de siste sju dagene")
                                .font(.footnote).foregroundStyle(.secondary)
                                .listRowSeparator(.hidden)
                        }
                        if valgt == .fast {
                            Text("Utstillinger uten datoer – står inntil videre")
                                .font(.footnote).foregroundStyle(.secondary)
                                .listRowSeparator(.hidden)
                        }
                        if valgt == .arrangement {
                            Text("Omvisninger, samtaler og konserter den kommende måneden")
                                .font(.footnote).foregroundStyle(.secondary)
                                .listRowSeparator(.hidden)
                        }
                        ForEach(liste) { u in
                            NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle(fast?.rawValue ?? "Galleriradar")
            .navigationDestination(for: Utstilling.self) { DetaljVisning(utstilling: $0) }
            .searchable(text: $sok, prompt: "Kunstner, tittel eller galleri")
            .refreshable { await lager.hent(tving: true) }
            .toolbar {
                if fast == nil {
                    ToolbarItem(placement: .principal) {
                        Picker("Visning", selection: $visning) {
                            ForEach([Lager.Visning.naa, .nytt, .kommer, .fast]) { Text($0.rawValue).tag($0) }
                        }
                        .pickerStyle(.segmented)
                    }
                }
            }
        }
    }
}

private struct Tomtrom: View {
    let visning: Lager.Visning
    let laster: Bool

    var body: some View {
        if laster {
            ProgressView("Henter utstillinger …")
        } else {
            ContentUnavailableView(
                visning == .nytt ? "Ingenting nytt"
                    : visning == .arrangement ? "Ingen arrangementer"
                    : visning == .merket ? "Min liste er tom" : "Ingen utstillinger",
                systemImage: visning == .merket ? "star"
                    : visning == .arrangement ? "calendar" : "paintpalette",
                description: Text(visning == .nytt
                    ? "Ingen utstillinger har åpnet de siste sju dagene."
                    : visning == .arrangement
                        ? "Ingenting står på programmet den kommende måneden."
                        : visning == .merket
                            ? "Trykk «Legg i min liste» på en utstilling for å samle den her."
                            : "Dra ned for å hente på nytt."))
        }
    }
}

struct Utstillingsrad: View {
    @EnvironmentObject private var lager: Lager
    let utstilling: Utstilling

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Miniatyr(adresse: utstilling.bildeadresse)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(utstilling.galleri.uppercased())
                        .font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                    if lager.erNy(utstilling) { Merkelapp(tekst: "NY") }
                }
                Text(utstilling.tittel)
                    .font(.system(.headline, design: .serif)).lineLimit(2)
                if let k = utstilling.kunstnere, !k.isEmpty {
                    Text(k).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                }
                HStack(spacing: 6) {
                    Text(utstilling.periode ?? "").font(.caption).foregroundStyle(.secondary)
                    if !utstilling.erArrangement, let d = utstilling.dagerIgjen(), d <= 7 {
                        Text(d == 0 ? "Siste dag" : d == 1 ? "Siste dag i morgen" : "\(d) dager igjen")
                            .font(.caption.weight(.semibold)).foregroundStyle(Color.aksent)
                    }
                }
            }
            Spacer(minLength: 0)
            if lager.erMerket(utstilling) {
                Image(systemName: "star.fill").font(.caption).foregroundStyle(Color.aksent)
            }
        }
        .padding(.vertical, 4)
    }
}

struct Merkelapp: View {
    let tekst: String
    var body: some View {
        Text(tekst)
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(Color.aksent, in: Capsule())
            .foregroundStyle(.white)
    }
}

struct Miniatyr: View {
    let adresse: URL?
    var body: some View {
        AsyncImage(url: adresse) { bilde in
            bilde.resizable().scaledToFill()
        } placeholder: {
            Rectangle().fill(Color.aksent.opacity(0.12))
        }
        .frame(width: 78, height: 78)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - detaljer

struct DetaljVisning: View {
    @EnvironmentObject private var lager: Lager
    let utstilling: Utstilling
    @State private var kalenderbeskjed: String?
    @State private var arkiv = EKEventStore()
    @State private var forslag: EKEvent?
    @State private var visKalender = false

    private var sted: Sted? { lager.sted(for: utstilling.kildeId) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let a = utstilling.bildeadresse {
                    AsyncImage(url: a) { $0.resizable().scaledToFit() } placeholder: {
                        Rectangle().fill(Color.aksent.opacity(0.12)).frame(height: 200)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(utstilling.galleri.uppercased())
                        .font(.caption).foregroundStyle(.secondary)
                    Text(utstilling.tittel).font(.system(.title2, design: .serif).weight(.semibold))
                    if let k = utstilling.kunstnere, !k.isEmpty {
                        Text(k).font(.headline).foregroundStyle(.secondary)
                    }
                    Text(utstilling.periode ?? "").font(.subheadline)
                    if let d = utstilling.dagerIgjen(), d <= 14 {
                        // Et arrangement har ingen «siste dag» – det skjer den dagen.
                        Text(utstilling.erArrangement
                             ? (d == 0 ? "I dag" : d == 1 ? "I morgen" : "Om \(d) dager")
                             : (d == 0 ? "Siste dag i dag" : d == 1 ? "Siste dag i morgen"
                                : "\(d) dager igjen"))
                            .font(.subheadline.weight(.semibold)).foregroundStyle(Color.aksent)
                    }
                }

                if let s = utstilling.sammendrag, !s.isEmpty {
                    Text(s).font(.body)
                }

                if let sted, let adresse = sted.adresse, !adresse.isEmpty {
                    Label(adresse, systemImage: "mappin.and.ellipse")
                        .font(.subheadline).foregroundStyle(.secondary)
                }

                VStack(spacing: 10) {
                    // Den viktigste knappen først, og den sier hva den gjør.
                    Button { lager.veksleMerke(utstilling) } label: {
                        Knappetekst(
                            tekst: lager.erMerket(utstilling) ? "Fjern fra min liste" : "Legg i min liste",
                            ikon: lager.erMerket(utstilling) ? "star.fill" : "star",
                            fylt: lager.erMerket(utstilling))
                    }

                    if let lenke = utstilling.lenke {
                        Link(destination: lenke) {
                            Knappetekst(tekst: "Åpne hos \(utstilling.galleri)", ikon: "safari")
                        }
                    }
                    // Bare arrangementer hører hjemme i kalenderen. En utstilling
                    // som står i tre måneder er ingen avtale.
                    if utstilling.erArrangement && utstilling.start != nil {
                        Button { leggIKalender() } label: {
                            Knappetekst(tekst: "Foreslå i kalenderen", ikon: "calendar.badge.plus")
                        }
                    }

                    if let sted, sted.harPosisjon {
                        Button { visIKart(sted) } label: {
                            Knappetekst(tekst: "Vis veien", ikon: "map")
                        }
                    }
                }
                .padding(.top, 4)

                if let beskjed = kalenderbeskjed {
                    Text(beskjed).font(.footnote).foregroundStyle(.secondary)
                }
            }
            .padding()
        }
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $visKalender) {
            if let forslag {
                KalenderRedigering(hendelse: forslag, arkiv: arkiv)
                    .ignoresSafeArea()
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { lager.veksleMerke(utstilling) } label: {
                    Image(systemName: lager.erMerket(utstilling) ? "star.fill" : "star")
                }
                .tint(.aksent)
            }
            if let lenke = utstilling.lenke {
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: lenke) { Image(systemName: "square.and.arrow.up") }
                }
            }
        }
    }

    private func visIKart(_ sted: Sted) {
        guard let lat = sted.lat, let lon = sted.lon else { return }
        let punkt = MKPlacemark(coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon))
        let mål = MKMapItem(placemark: punkt)
        mål.name = sted.navn
        mål.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeWalking])
    }

    /// Fyller ut et forslag og lar Kalender-appen vise det fram. Ingenting
    /// havner i kalenderen før du selv trykker «Legg til».
    private func leggIKalender() {
        let adresse = sted?.adresse
        arkiv.requestWriteOnlyAccessToEvents { fikkLov, _ in
            DispatchQueue.main.async {
                guard fikkLov else {
                    kalenderbeskjed = "Appen mangler tilgang til kalenderen. "
                        + "Du kan gi den i Innstillinger → Personvern → Kalendere."
                    return
                }
                let hendelse = EKEvent(eventStore: arkiv)
                hendelse.title = "\(utstilling.tittel) – \(utstilling.galleri)"
                hendelse.isAllDay = true
                let fra = utstilling.start ?? utstilling.slutt ?? Date()
                hendelse.startDate = fra
                hendelse.endDate = utstilling.slutt ?? fra
                hendelse.location = adresse
                hendelse.notes = [utstilling.kunstnere, utstilling.sammendrag, utstilling.url]
                    .compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: "\n\n")
                hendelse.calendar = arkiv.defaultCalendarForNewEvents
                forslag = hendelse
                visKalender = true
            }
        }
    }
}

/// Apples egen hendelsesredigerer. Den viser forslaget ferdig utfylt, og
/// brukeren avgjør selv om det skal lagres.
struct KalenderRedigering: UIViewControllerRepresentable {
    let hendelse: EKEvent
    let arkiv: EKEventStore
    @Environment(\.dismiss) private var lukk

    func makeUIViewController(context: Context) -> EKEventEditViewController {
        let vis = EKEventEditViewController()
        vis.event = hendelse
        vis.eventStore = arkiv
        vis.editViewDelegate = context.coordinator
        return vis
    }

    func updateUIViewController(_ vis: EKEventEditViewController, context: Context) {}

    func makeCoordinator() -> Ordstyrer { Ordstyrer { lukk() } }

    final class Ordstyrer: NSObject, EKEventEditViewDelegate {
        private let lukk: () -> Void
        init(lukk: @escaping () -> Void) { self.lukk = lukk }

        func eventEditViewController(_ vis: EKEventEditViewController,
                                     didCompleteWith action: EKEventEditViewAction) {
            lukk()
        }
    }
}

private struct Knappetekst: View {
    let tekst: String
    let ikon: String
    var fylt = false

    var body: some View {
        HStack {
            Image(systemName: ikon)
            Text(tekst).fontWeight(fylt ? .semibold : .regular)
            Spacer()
            if !fylt {
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 12).padding(.horizontal, 14)
        .background(fylt ? Color.aksent : Color.aksent.opacity(0.10),
                    in: RoundedRectangle(cornerRadius: 10))
        .foregroundStyle(fylt ? .white : Color.aksent)
    }
}

// MARK: - kart

/// Flere visningssteder som ligger for tett til å vises hver for seg ved
/// gjeldende zoom. Klyngen viser samlet antall, og åpner seg når man trykker.
private struct Klynge: Identifiable {
    let id: String
    let posisjon: CLLocationCoordinate2D
    let steder: [(sted: Sted, antall: Int)]

    var antall: Int { steder.reduce(0) { $0 + $1.antall } }
    var eneste: Sted? { steder.count == 1 ? steder[0].sted : nil }
    var navn: String { eneste?.navn ?? "\(steder.count) steder" }

    /// Utsnittet som rommer alle stedene i klyngen, med litt luft rundt.
    var omraade: MKCoordinateRegion {
        let punkter = steder.compactMap { s -> CLLocationCoordinate2D? in
            guard let lat = s.sted.lat, let lon = s.sted.lon else { return nil }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
        let breddegrader = punkter.map(\.latitude)
        let lengdegrader = punkter.map(\.longitude)
        let minB = breddegrader.min() ?? posisjon.latitude
        let maksB = breddegrader.max() ?? posisjon.latitude
        let minL = lengdegrader.min() ?? posisjon.longitude
        let maksL = lengdegrader.max() ?? posisjon.longitude
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: (minB + maksB) / 2,
                                           longitude: (minL + maksL) / 2),
            span: MKCoordinateSpan(latitudeDelta: max((maksB - minB) * 2.2, 0.006),
                                   longitudeDelta: max((maksL - minL) * 2.2, 0.006)))
    }
}

struct KartVisning: View {
    @EnvironmentObject private var lager: Lager
    @State private var utsnitt = MapCameraPosition.region(
        MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 59.9139, longitude: 10.7400),
                           span: MKCoordinateSpan(latitudeDelta: 0.042, longitudeDelta: 0.042)))
    @State private var span = MKCoordinateSpan(latitudeDelta: 0.042, longitudeDelta: 0.042)
    @State private var valgt: Sted?

    /// Deler kartet i ruter som følger zoomnivået, og slår sammen stedene som
    /// havner i samme rute. Zoomer man inn, deler klyngene seg av seg selv.
    private var klynger: [Klynge] {
        let celle = max(span.latitudeDelta / 7, 0.0004)
        // Lengdegrader ligger tettere jo lenger nord man er – på Oslos
        // breddegrad er én grad øst-vest omtrent halvparten så lang.
        let celleLengde = celle * 2

        var bøtter: [String: [(sted: Sted, antall: Int)]] = [:]
        for par in lager.stederMedProgram() {
            guard let lat = par.sted.lat, let lon = par.sted.lon else { continue }
            let nøkkel = "\(Int((lat / celle).rounded(.down)))_\(Int((lon / celleLengde).rounded(.down)))"
            bøtter[nøkkel, default: []].append(par)
        }

        return bøtter.map { nøkkel, gruppe in
            let lat = gruppe.compactMap { $0.sted.lat }.reduce(0, +) / Double(gruppe.count)
            let lon = gruppe.compactMap { $0.sted.lon }.reduce(0, +) / Double(gruppe.count)
            return Klynge(id: nøkkel,
                          posisjon: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                          steder: gruppe)
        }
        .sorted { $0.id < $1.id }
    }

    var body: some View {
        NavigationStack {
            Map(position: $utsnitt) {
                ForEach(klynger) { klynge in
                    Annotation(klynge.navn, coordinate: klynge.posisjon) {
                        Button {
                            if let sted = klynge.eneste {
                                valgt = sted
                            } else {
                                withAnimation { utsnitt = .region(klynge.omraade) }
                            }
                        } label: {
                            Text("\(klynge.antall)")
                                .font(.system(size: klynge.steder.count > 1 ? 13 : 11,
                                              weight: .bold))
                                .frame(width: klynge.steder.count > 1 ? 30 : 22,
                                       height: klynge.steder.count > 1 ? 30 : 22)
                                .background(Color.aksent, in: Circle())
                                .overlay(Circle().stroke(.white, lineWidth: 1.5))
                                .foregroundStyle(.white)
                                .shadow(radius: 1.5, y: 1)
                        }
                    }
                }
            }
            .onMapCameraChange(frequency: .onEnd) { ramme in
                span = ramme.region.span
            }
            .navigationTitle("Kart")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(item: $valgt) { sted in
                NavigationStack {
                    StedsListe(sted: sted)
                        .navigationTitle(sted.navn)
                        .navigationBarTitleDisplayMode(.inline)
                        .navigationDestination(for: Utstilling.self) { DetaljVisning(utstilling: $0) }
                }
                .presentationDetents([.medium, .large])
            }
        }
    }
}

/// Alt som skjer på ett sted: utstillingene øverst, arrangementene under.
struct StedsListe: View {
    @EnvironmentObject private var lager: Lager
    let sted: Sted

    var body: some View {
        let innhold = lager.paaSted(sted.id)
        List {
            if !innhold.utstillinger.isEmpty {
                Section("Utstillinger") {
                    ForEach(innhold.utstillinger) { u in
                        NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
                    }
                }
            }
            if !innhold.arrangementer.isEmpty {
                Section("Arrangementer") {
                    ForEach(innhold.arrangementer) { u in
                        NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
                    }
                }
            }
            if innhold.utstillinger.isEmpty && innhold.arrangementer.isEmpty {
                Text("Ingenting på plakaten akkurat nå.").foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - om

struct OmVisning: View {
    @EnvironmentObject private var lager: Lager
    @State private var varsling = Varsler.påskrudd

    var body: some View {
        NavigationStack {
            List {
                Section("Varsler") {
                    Toggle("Si fra om nye utstillinger", isOn: $varsling)
                        .tint(.aksent)
                        .onChange(of: varsling) { _, ny in
                            Varsler.påskrudd = ny
                            if ny { Task { _ = await Varsler.spørOmLov() } }
                        }
                    Text("Appen ser etter nytt i bakgrunnen. iOS bestemmer selv når den får lov, gjerne et par ganger i døgnet.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Listen") {
                    Rad(navn: "Utstillinger", verdi: "\(lager.data.antall)")
                    Rad(navn: "Visningssteder", verdi: "\(lager.data.kilder.count)")
                    if !lager.data.bygget.isEmpty {
                        Rad(navn: "Sist hentet", verdi: Dato.lesbart(lager.data.bygget))
                    }
                    Button("Hent på nytt nå") { Task { await lager.hent(tving: true) } }
                        .foregroundStyle(Color.aksent)
                }

                // Huk av stedene dere vil følge. Alt er med til dere sier noe annet.
                ForEach(Datasett.regionrekke.filter { !lager.data.stederIRegion($0).isEmpty },
                        id: \.self) { region in
                    let steder = lager.data.stederIRegion(region)
                    let paa = steder.filter { lager.erPaa($0.id) }.count
                    Section {
                        // Hele regionen i én bevegelse.
                        Toggle(isOn: Binding(
                            get: { paa > 0 },
                            set: { lager.settRegion(region, pa: $0) })) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Hele \(lager.data.regionNavn(region))")
                                        .fontWeight(.semibold)
                                    Text(paa == steder.count
                                         ? (steder.count == 1 ? "1 sted" : "\(steder.count) steder")
                                         : "\(paa) av \(steder.count) steder")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            .tint(.aksent)

                        DisclosureGroup("Velg enkeltsteder") {
                            ForEach(steder) { sted in
                                Toggle(isOn: Binding(
                                    get: { lager.erPaa(sted.id) },
                                    set: { _ in lager.veksleKilde(sted.id) })) {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(sted.navn)
                                            HStack(spacing: 6) {
                                                if let a = sted.adresse, !a.isEmpty {
                                                    Text(a).lineLimit(1)
                                                }
                                                if sted.feil != nil || sted.antall == 0 {
                                                    Text("henter ingenting nå").foregroundStyle(.orange)
                                                }
                                            }
                                            .font(.caption).foregroundStyle(.secondary)
                                        }
                                    }
                                    .tint(.aksent)
                            }
                        }
                        .tint(.aksent)
                    } header: {
                        Text(lager.data.regionNavn(region))
                    }
                }

                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Utstillingene hentes fra galleriene selv, fire ganger i døgnet.")
                        Text("Appen er utviklet av Gladesigner. En bedrift opptatt av kunst og kultur siden 2007.")
                    }
                    .font(.footnote).foregroundStyle(.secondary)
                    .padding(.vertical, 2)
                }
            }
            .navigationTitle("Om")
        }
    }

    private struct Rad: View {
        let navn: String
        let verdi: String
        var body: some View {
            HStack { Text(navn); Spacer(); Text(verdi).foregroundStyle(.secondary) }
        }
    }
}
