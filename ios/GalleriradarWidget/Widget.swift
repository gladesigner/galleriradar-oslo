import SwiftUI
import WidgetKit

struct Innslag: TimelineEntry {
    let date: Date
    let utstillinger: [Utstilling]
    let antallNaa: Int

    static let eksempel = Innslag(date: Date(), utstillinger: [], antallNaa: 0)
}

struct Leverandør: TimelineProvider {
    func placeholder(in context: Context) -> Innslag { .eksempel }

    func getSnapshot(in context: Context, completion: @escaping (Innslag) -> Void) {
        Task { completion(await hent()) }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Innslag>) -> Void) {
        Task {
            let innslag = await hent()
            // Litt oftere enn jobben hos GitHub, så widgeten sjelden er langt bak.
            let neste = Date(timeIntervalSinceNow: 2 * 3600)
            completion(Timeline(entries: [innslag], policy: .after(neste)))
        }
    }

    /// Widgeten henter listen selv. Den deler ikke lager med appen, men det er
    /// billig nok: data.json er én fil, og iOS hurtiglagrer den.
    private func hent() async -> Innslag {
        guard let (raa, _) = try? await URLSession.shared.data(from: Tjeneste.data(friskt: true)),
              let d = try? JSONDecoder().decode(Datasett.self, from: raa) else {
            return .eksempel
        }
        let iDag = d.iDag
        let naa = d.utstillinger
            .filter { ($0.borte ?? false) == false
                && ($0.sluttDato == nil || $0.sluttDato! >= iDag)
                && ($0.startDato == nil || $0.startDato! <= iDag) }
            .sorted { ($0.sluttDato ?? "9999") < ($1.sluttDato ?? "9999") }
        return Innslag(date: Date(), utstillinger: Array(naa.prefix(4)), antallNaa: naa.count)
    }
}

struct WidgetVisning: View {
    @Environment(\.widgetFamily) private var størrelse
    let innslag: Innslag

    private var antall: Int { størrelse == .systemSmall ? 1 : størrelse == .systemLarge ? 4 : 3 }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 5) {
                Circle().fill(Color.widgetAksent).frame(width: 6, height: 6)
                Text("GALLERIRADAR").font(.system(size: 9, weight: .semibold)).kerning(0.6)
                Spacer()
                if innslag.antallNaa > 0 {
                    Text("\(innslag.antallNaa)").font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(.secondary)
                }
            }
            .foregroundStyle(.secondary)

            if innslag.utstillinger.isEmpty {
                Text("Ingen utstillinger hentet ennå")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                ForEach(innslag.utstillinger.prefix(antall), id: \.nokkel) { u in
                    VStack(alignment: .leading, spacing: 1) {
                        Text(u.tittel)
                            .font(.system(size: størrelse == .systemSmall ? 13 : 14,
                                          weight: .semibold, design: .serif))
                            .lineLimit(2)
                        HStack(spacing: 4) {
                            Text(u.galleri).font(.system(size: 10)).foregroundStyle(.secondary)
                                .lineLimit(1)
                            if let d = u.dagerIgjen(), d <= 7 {
                                Text(d == 0 ? "siste dag" : "\(d) d igjen")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundStyle(Color.widgetAksent)
                            }
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .containerBackground(for: .widget) { Color.widgetPapir }
    }
}

extension Color {
    static let widgetAksent = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 0.878, green: 0.541, blue: 0.416, alpha: 1)
        : UIColor(red: 0.604, green: 0.231, blue: 0.133, alpha: 1) })
    static let widgetPapir = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 0.075, green: 0.071, blue: 0.063, alpha: 1)
        : UIColor(red: 0.965, green: 0.957, blue: 0.941, alpha: 1) })
}

struct GalleriradarWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "GalleriradarWidget", provider: Leverandør()) { innslag in
            WidgetVisning(innslag: innslag)
        }
        .configurationDisplayName("Galleriradar")
        .description("Utstillingene som går nå i Oslo.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

@main
struct GalleriradarWidgetBundle: WidgetBundle {
    var body: some Widget { GalleriradarWidget() }
}
