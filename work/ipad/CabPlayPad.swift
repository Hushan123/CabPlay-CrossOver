import UIKit
import WebKit
import Network
import VisionKit
import AVFoundation

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication, configurationForConnecting session: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let configuration = UISceneConfiguration(name: nil, sessionRole: session.role)
        configuration.delegateClass = ScreenScene.self
        return configuration
    }
}

final class ScreenScene: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
        guard let scene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: scene)
        window.rootViewController = CabPlayScreen()
        self.window = window
        window.makeKeyAndVisible()
    }

    func sceneDidBecomeActive(_ scene: UIScene) {
        UIApplication.shared.isIdleTimerDisabled = true
    }

    func sceneWillResignActive(_ scene: UIScene) {
        UIApplication.shared.isIdleTimerDisabled = false
    }
}

final class CabPlayScreen: UIViewController, WKNavigationDelegate, DataScannerViewControllerDelegate {
    private let usb = USBDisplay()
    private var probe: NWConnection?
    private var wired = false
    private let monitor = NWPathMonitor()
    private let webView = WKWebView()
    private let addressKey = "cabplayAddress"
    private var address: URL?
    private var started = false

    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }

    override func loadView() {
        view = UIView()
        view.backgroundColor = .black
        for child in [webView as UIView, usb] {
            child.frame = view.bounds
            child.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(child)
        }
        usb.isHidden = true
        usb.onConnection = { [weak self] connected in
            guard let self else { return }
            self.usb.isHidden = !connected
            self.webView.isHidden = connected
            if connected {
                self.presentedViewController?.dismiss(animated: false)
                self.webView.loadHTMLString("", baseURL: nil)
            } else if let url = self.address {
                self.connect(url)
            } else {
                self.prompt("连接 USB 数据线可自动连接，或扫描、输入无线配对网址。")
            }
        }
        usb.listen()
        webView.backgroundColor = .black
        webView.isOpaque = false
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.navigationDelegate = self
        monitor.pathUpdateHandler = { [weak self] _ in
            DispatchQueue.main.async {
                if let self, let url = self.address { self.checkRoute(url) }
            }
        }
        monitor.start(queue: .main)

        let settings = UILongPressGestureRecognizer(target: self, action: #selector(changeAddress(_:)))
        settings.numberOfTouchesRequired = 2
        webView.addGestureRecognizer(settings)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !started else { return }
        started = true
        if let saved = UserDefaults.standard.string(forKey: addressKey), let url = pairingURL(saved) {
            connect(url)
        } else {
            prompt("粘贴 CabPlay「手机控制」里显示的完整配对网址。之后会自动连接。双指长按可更换地址。")
        }
    }

    private func pairingURL(_ text: String) -> URL? {
        guard let parts = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let host = parts.host, !host.isEmpty,
              parts.scheme == "http" || parts.scheme == "https",
              parts.user == nil, parts.password == nil,
              parts.queryItems?.contains(where: { $0.name == "t" && !($0.value ?? "").isEmpty }) == true
        else { return nil }
        return parts.url
    }

    private func checkRoute(_ url: URL) {
        probe?.cancel()
        wired = false
        updateProfile()
        if let host = url.host, let port = NWEndpoint.Port(rawValue: UInt16(exactly: url.port ?? (url.scheme == "https" ? 443 : 80)) ?? 0), port.rawValue > 0 {
            let connection = NWConnection(host: NWEndpoint.Host(host), port: port, using: .tcp)
            probe = connection
            connection.pathUpdateHandler = { [weak self, weak connection] path in
                DispatchQueue.main.async {
                    guard let self, self.probe === connection else { return }
                    self.wired = path.status == .satisfied && path.usesInterfaceType(.wiredEthernet)
                    self.updateProfile()
                }
            }
            connection.stateUpdateHandler = { [weak self, weak connection] state in
                guard case .ready = state, let self, let connection, self.probe === connection else { return }
                self.wired = connection.currentPath?.usesInterfaceType(.wiredEthernet) == true
                self.updateProfile()
                self.probe = nil
                connection.cancel()
            }
            connection.start(queue: .main)
        }
    }

    private func connect(_ url: URL) {
        address = url
        checkRoute(url)
        UserDefaults.standard.set(url.absoluteString, forKey: addressKey)
        webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
    }

    private func updateProfile() {
        webView.evaluateJavaScript("window.cabPlayWired = " + (wired ? "true" : "false"))
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { updateProfile() }

    private func scan() {
        AVCaptureDevice.requestAccess(for: .video) { allowed in
            DispatchQueue.main.async {
                guard allowed, DataScannerViewController.isSupported, DataScannerViewController.isAvailable else {
                    self.prompt("相机不可用，可手动输入配对网址。")
                    return
                }
                let scanner = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])])
                scanner.delegate = self
                let nav = UINavigationController(rootViewController: scanner)
                scanner.navigationItem.title = "扫描 CabPlay 配对码"
                scanner.navigationItem.leftBarButtonItem = UIBarButtonItem(barButtonSystemItem: .cancel, target: self, action: #selector(self.cancelScan))
                nav.modalPresentationStyle = .fullScreen
                self.present(nav, animated: true) {
                    do { try scanner.startScanning() }
                    catch { self.cancelScan() }
                }
            }
        }
    }

    @objc private func cancelScan() {
        dismiss(animated: true) { self.prompt("扫描二维码或手动输入完整配对网址。") }
    }

    func dataScanner(_ scanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
        for item in addedItems {
            if case .barcode(let code) = item, let text = code.payloadStringValue, let url = pairingURL(text),
               scanner.isScanning {
                scanner.stopScanning()
                dismiss(animated: true) { self.connect(url) }
                return
            }
        }
    }

    @objc private func changeAddress(_ gesture: UILongPressGestureRecognizer) {
        if gesture.state == .began { prompt("粘贴新的配对网址，或用当前地址重新连接。") }
    }

    private func prompt(_ message: String) {
        guard usb.isHidden, presentedViewController == nil else { return }
        let alert = UIAlertController(title: "连接 CabPlay", message: message, preferredStyle: .alert)
        alert.addTextField { field in
            field.placeholder = "http://局域网地址:端口/?t=…"
            field.text = self.address?.absoluteString
            field.keyboardType = .URL
            field.autocorrectionType = .no
            field.autocapitalizationType = .none
        }
        alert.addAction(UIAlertAction(title: "扫描二维码", style: .default) { _ in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.scan() }
        })
        if address != nil {
            alert.addAction(UIAlertAction(title: "取消", style: .cancel))
        }
        alert.addAction(UIAlertAction(title: "连接", style: .default) { [weak self, weak alert] _ in
            guard let self else { return }
            if let text = alert?.textFields?.first?.text, let url = self.pairingURL(text) {
                self.connect(url)
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                    self.prompt("请粘贴带配对参数的完整网址。")
                }
            }
        })
        present(alert, animated: true)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        prompt("请确认 Mac 上的 CabPlay 已开启手机控制，且 iPad 能通过无线或有线局域网访问 Mac。")
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        if let address { connect(address) }
    }
}
