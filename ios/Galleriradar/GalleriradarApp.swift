import SwiftUI
import WidgetKit

@main
struct GalleriradarApp: App {
    @StateObject private var lager = Lager()
    @Environment(\.scenePhase) private var fase

    init() {
        Varsler.registrer()
    }

    var body: some Scene {
        WindowGroup {
            Hovedvisning()
                .environmentObject(lager)
                .task {
                    await lager.hent()
                    _ = await Varsler.seEtterNytt()
                    Varsler.planlegg()
                    WidgetCenter.shared.reloadAllTimelines()
                }
        }
        .onChange(of: fase) { _, ny in
            if ny == .active {
                Task { await lager.hent() }
            } else if ny == .background {
                Varsler.planlegg()
            }
        }
    }
}
