import SafariServices
import SwiftUI

/// Stedets egen side, vist oppå appen.
///
/// SFSafariViewController er Apples egen nettleser i miniatyr: lesevisning,
/// deling og en «Lukk»-knapp. Man får hele siden uten å forlate appen, og er
/// tilbake der man slapp med ett trykk.
struct Nettvindu: UIViewControllerRepresentable {
    let adresse: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let oppsett = SFSafariViewController.Configuration()
        oppsett.entersReaderIfAvailable = false      // gallerisider er bilder, ikke brødtekst
        let vis = SFSafariViewController(url: adresse, configuration: oppsett)
        vis.preferredControlTintColor = UIColor(Color.aksent)
        vis.dismissButtonStyle = .close
        return vis
    }

    func updateUIViewController(_ vis: SFSafariViewController, context: Context) {}
}

/// En URL som kan brukes i .sheet(item:). URL er ikke Identifiable selv.
struct Nettadresse: Identifiable {
    let url: URL
    var id: String { url.absoluteString }

    /// SFSafariViewController tar bare http og https. Alt annet må til systemet.
    init?(_ url: URL?) {
        guard let url, let s = url.scheme?.lowercased(), s == "http" || s == "https" else { return nil }
        self.url = url
    }
}
