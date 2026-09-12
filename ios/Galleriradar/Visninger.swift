import EventKit
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

    var body: some View {
        TabView {
            ListeVisning()
                .tabItem { Label("Utstillinger", systemImage: "square.grid.2x2") }
                .badge(lager.antall(.nytt))

            KartVisning()
                .tabItem { Label("Kart", systemImage: "map") }

            ListeVisning(fast: .merket)
                .tabItem { Label("Vil se", systemImage: "star") }

            OmVisning()
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
                            Section {
                                Button("Merk alt som sett") { lager.merkAltSomSett() }
                                    .foregroundStyle(Color.aksent)
                            }
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
                            ForEach([Lager.Visning.naa, .nytt, .kommer]) { Text($0.rawValue).tag($0) }
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
                visning == .nytt ? "Ingenting nytt" : "Ingen utstillinger",
                systemImage: visning == .merket ? "star" : "paintpalette",
                description: Text(visning == .nytt
                    ? "Du får varsel når noe dukker opp."
                    : visning == .merket
                        ? "Trykk stjerna på en utstilling for å samle den her."
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
                    if let d = utstilling.dagerIgjen(), d <= 7 {
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
                        Text(d == 0 ? "Siste dag i dag" : d == 1 ? "Siste dag i morgen" : "\(d) dager igjen")
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
                    if let lenke = utstilling.lenke {
                        Link(destination: lenke) {
                            Knappetekst(tekst: "Åpne hos \(utstilling.galleri)", ikon: "safari")
                        }
                    }
                    Button { leggIKalender() } label: {
                        Knappetekst(tekst: "Legg i kalender", ikon: "calendar.badge.plus")
                    }
                    .disabled(utstilling.start == nil && utstilling.slutt == nil)

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

    private func leggIKalender() {
        let arkiv = EKEventStore()
        let adresse = sted?.adresse          // hentes her, ikke inne i tilbakekallet
        arkiv.requestWriteOnlyAccessToEvents { fikkLov, _ in
            guard fikkLov else {
                DispatchQueue.main.async { kalenderbeskjed = "Appen mangler tilgang til kalenderen." }
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
            do {
                try arkiv.save(hendelse, span: .thisEvent)
                DispatchQueue.main.async { kalenderbeskjed = "Lagt i kalenderen." }
            } catch {
                DispatchQueue.main.async { kalenderbeskjed = "Fikk ikke lagret i kalenderen." }
            }
        }
    }
}

private struct Knappetekst: View {
    let tekst: String
    let ikon: String
    var body: some View {
        HStack {
            Image(systemName: ikon)
            Text(tekst)
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 12).padding(.horizontal, 14)
        .background(Color.aksent.opacity(0.10), in: RoundedRectangle(cornerRadius: 10))
        .foregroundStyle(Color.aksent)
    }
}

// MARK: - kart

struct KartVisning: View {
    @EnvironmentObject private var lager: Lager
    @State private var utsnitt = MapCameraPosition.region(
        MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 59.9139, longitude: 10.7400),
                           span: MKCoordinateSpan(latitudeDelta: 0.042, longitudeDelta: 0.042)))
    @State private var valgt: Sted?

    var body: some View {
        NavigationStack {
            Map(position: $utsnitt) {
                ForEach(lager.stederMedProgram(), id: \.sted.id) { par in
                    if let lat = par.sted.lat, let lon = par.sted.lon {
                        Annotation(par.sted.navn,
                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon)) {
                            Button { valgt = par.sted } label: {
                                Text("\(par.utstillinger.count)")
                                    .font(.system(size: 11, weight: .bold))
                                    .frame(width: 22, height: 22)
                                    .background(Color.aksent, in: Circle())
                                    .overlay(Circle().stroke(.white, lineWidth: 1.5))
                                    .foregroundStyle(.white)
                                    .shadow(radius: 1.5, y: 1)
                            }
                        }
                        .annotationTitles(.automatic)
                    }
                }
            }
            .navigationTitle("Kart")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(item: $valgt) { sted in
                NavigationStack {
                    List(lager.utstillinger(.naa, sted: sted.id)) { u in
                        NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
                    }
                    .navigationTitle(sted.navn)
                    .navigationBarTitleDisplayMode(.inline)
                    .navigationDestination(for: Utstilling.self) { DetaljVisning(utstilling: $0) }
                }
                .presentationDetents([.medium, .large])
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

                Section("Kilder") {
                    ForEach(lager.data.kilder) { s in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(s.navn)
                                if let a = s.adresse, !a.isEmpty {
                                    Text(a).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            if s.feil != nil || s.antall == 0 {
                                Image(systemName: "exclamationmark.triangle")
                                    .foregroundStyle(.orange)
                            } else {
                                Text("\(s.antall)").foregroundStyle(.secondary)
                                    .monospacedDigit()
                            }
                        }
                    }
                }

                Section {
                    Text("Utstillingene hentes fra galleriene selv, fire ganger i døgnet.")
                        .font(.footnote).foregroundStyle(.secondary)
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
