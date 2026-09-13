import SwiftUI

/// Månedskalender: velg en dato, få dagens program under.
///
/// En liste svarer på «hva skjer framover». Et rutenett svarer på «hva skjer
/// den lørdagen jeg er ledig» – og det er et annet spørsmål. Utstillinger
/// står i måneder og hører ikke hjemme her, men dagen de åpner og dagen de
/// tas ned er faste punkter, og de tas med.
struct KalenderVisning: View {
    @EnvironmentObject private var lager: Lager
    @State private var måned = Kalenderen.månedsstart(Date())
    @State private var valgt = Dato.tekst(Date())

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Månedsrutenett(måned: $måned, valgt: $valgt,
                                   dagerMedNoe: lager.dagerMedNoe())
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)
                        .listRowSeparator(.hidden)
                }
                let dagens = lager.paaDato(valgt)
                if dagens.erTom {
                    Section(Dato.langDagtekst(valgt)) {
                        Text("Ingenting denne dagen.").foregroundStyle(.secondary)
                    }
                }
                Bolk(tittel: Dato.langDagtekst(valgt), rader: dagens.arrangementer)
                Bolk(tittel: "Åpner", rader: dagens.apner)
                Bolk(tittel: "Siste dag", rader: dagens.slutter)

                // Kalenderen svarer på én dag om gangen. Noen ganger vil man
                // se hele rekka, og da er den her.
                Section {
                    NavigationLink {
                        ArrangementsListe()
                    } label: {
                        Label("Alle arrangementer framover", systemImage: "list.bullet")
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Kalender")
            .navigationDestination(for: Utstilling.self) { DetaljVisning(utstilling: $0) }
            .refreshable { await lager.hent(tving: true) }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("I dag") {
                        valgt = lager.data.iDag.isEmpty ? Dato.tekst(Date()) : lager.data.iDag
                        måned = Kalenderen.månedsstart(Dato.fra(valgt) ?? Date())
                    }
                }
            }
        }
    }
}

/// Hele rekka av arrangementer, uten kalenderen rundt.
private struct ArrangementsListe: View {
    @EnvironmentObject private var lager: Lager

    var body: some View {
        List(lager.utstillinger(.arrangement)) { u in
            NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
        }
        .listStyle(.plain)
        .navigationTitle("Arrangementer")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// En bolk vises bare når den har noe i seg.
private struct Bolk: View {
    let tittel: String
    let rader: [Utstilling]

    var body: some View {
        if !rader.isEmpty {
            Section(tittel) {
                ForEach(rader) { u in
                    NavigationLink(value: u) { Utstillingsrad(utstilling: u) }
                }
            }
        }
    }
}

/// Selve rutenettet. Mandag først, slik en norsk kalender leses.
struct Månedsrutenett: View {
    @Binding var måned: Date
    @Binding var valgt: String
    let dagerMedNoe: Set<String>

    private let ukedager = ["ma", "ti", "on", "to", "fr", "lø", "sø"]

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Knapp(ikon: "chevron.left") { flytt(-1) }
                Spacer()
                Text(Kalenderen.månedsnavn(måned))
                    .font(.headline)
                    .contentTransition(.numericText())
                Spacer()
                Knapp(ikon: "chevron.right") { flytt(1) }
            }

            HStack(spacing: 0) {
                ForEach(ukedager, id: \.self) { d in
                    Text(d).font(.caption2).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                }
            }

            ForEach(Kalenderen.uker(i: måned), id: \.first) { uke in
                HStack(spacing: 0) {
                    ForEach(uke, id: \.self) { dag in
                        if dag.isEmpty {
                            Color.clear.frame(maxWidth: .infinity, minHeight: 38)
                        } else {
                            Dagrute(dato: dag,
                                    valgt: dag == valgt,
                                    harNoe: dagerMedNoe.contains(dag))
                                .frame(maxWidth: .infinity)
                                .contentShape(Rectangle())
                                .onTapGesture { valgt = dag }
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }

    private func flytt(_ antall: Int) {
        withAnimation(.snappy) {
            måned = Calendar.current.date(byAdding: .month, value: antall, to: måned) ?? måned
        }
    }

    private struct Knapp: View {
        let ikon: String
        let gjør: () -> Void
        var body: some View {
            Button(action: gjør) {
                Image(systemName: ikon).font(.footnote.weight(.semibold))
                    .frame(width: 30, height: 30)
            }
            .buttonStyle(.bordered)
            .buttonBorderShape(.circle)
            .tint(.aksent)
        }
    }
}

private struct Dagrute: View {
    let dato: String
    let valgt: Bool
    let harNoe: Bool

    var body: some View {
        VStack(spacing: 3) {
            Text(Kalenderen.dagtall(dato))
                .font(.callout.monospacedDigit())
                .fontWeight(valgt ? .bold : .regular)
                .foregroundStyle(valgt ? Color.white : .primary)
                .frame(width: 30, height: 30)
                .background(valgt ? Color.aksent : .clear, in: Circle())
            // En prikk sier at dagen har noe, uten å fylle ruta med tall.
            Circle()
                .fill(harNoe ? Color.merke : .clear)
                .frame(width: 5, height: 5)
        }
        .frame(minHeight: 44)
    }
}

enum Kalenderen {
    static var kalender: Calendar {
        var k = Calendar(identifier: .gregorian)
        k.locale = Locale(identifier: "nb_NO")
        k.firstWeekday = 2                      // mandag
        return k
    }

    static func månedsstart(_ d: Date) -> Date {
        kalender.date(from: kalender.dateComponents([.year, .month], from: d)) ?? d
    }

    static func månedsnavn(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "nb_NO")
        f.dateFormat = "LLLL yyyy"
        let s = f.string(from: d)
        return s.prefix(1).uppercased() + s.dropFirst()
    }

    static func dagtall(_ iso: String) -> String {
        String(Int(iso.suffix(2)) ?? 0)
    }

    /// Månedens dager delt i uker, med tomme plasser før den første.
    static func uker(i måned: Date) -> [[String]] {
        let k = kalender
        let start = månedsstart(måned)
        guard let antall = k.range(of: .day, in: .month, for: start)?.count else { return [] }
        // firstWeekday er mandag, så mandag skal gi 0 tomme ruter.
        let forskyvning = (k.component(.weekday, from: start) - k.firstWeekday + 7) % 7

        var ruter = [String](repeating: "", count: forskyvning)
        for i in 0..<antall {
            if let d = k.date(byAdding: .day, value: i, to: start) {
                ruter.append(Dato.tekst(d))
            }
        }
        while ruter.count % 7 != 0 { ruter.append("") }
        return stride(from: 0, to: ruter.count, by: 7).map { Array(ruter[$0..<$0 + 7]) }
    }
}
