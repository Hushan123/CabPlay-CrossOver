import UIKit
import Network

final class USBDisplay: UIImageView {
    var onConnection: ((Bool) -> Void)?
    private var listener: NWListener?
    private var peer: NWConnection?
    private var active = false
    private var tracked: UITouch?

    func listen() {
        guard listener == nil else { return }
        contentMode = .scaleAspectFit
        backgroundColor = .black
        isUserInteractionEnabled = true
        let tcp = NWProtocolTCP.Options()
        tcp.noDelay = true
        let parameters = NWParameters(tls: nil, tcp: tcp)
        parameters.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: 48723)
        parameters.allowLocalEndpointReuse = true
        guard let server = try? NWListener(using: parameters) else { return }
        listener = server
        server.newConnectionHandler = { [weak self] c in self?.accept(c) }
        server.stateUpdateHandler = { [weak self] state in
            if case .failed = state {
                server.cancel()
                self?.listener = nil
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self?.listen() }
            }
        }
        server.start(queue: .main)
    }

    private func accept(_ connection: NWConnection) {
        guard peer == nil else { connection.cancel(); return }
        peer = connection
        connection.stateUpdateHandler = { [weak self] state in
            guard let self, self.peer === connection else { return }
            switch state {
            case .ready:
                self.send(Data("CABPAD12".utf8), connection)
                self.readHeader(connection)
            case .failed, .cancelled: self.close(connection)
            default: break
            }
        }
        connection.start(queue: .main)
    }

    private func close(_ connection: NWConnection) {
        guard peer === connection else { return }
        peer = nil
        connection.stateUpdateHandler = nil
        connection.cancel()
        image = nil
        tracked = nil
        if active { active = false; onConnection?(false) }
    }

    private func send(_ data: Data, _ connection: NWConnection) {
        connection.send(content: data, completion: .contentProcessed { [weak self] error in
            if error != nil { self?.close(connection) }
        })
    }

    private func read(_ count: Int, _ connection: NWConnection, _ completion: @escaping (Data) -> Void) {
        connection.receive(minimumIncompleteLength: count, maximumLength: count) { [weak self] data, _, _, error in
            guard let self, self.peer === connection else { return }
            guard error == nil, let data, data.count == count else { self.close(connection); return }
            completion(data)
        }
    }

    private func readHeader(_ connection: NWConnection) {
        read(4, connection) { header in
            let count = header.reduce(0) { ($0 << 8) | Int($1) }
            guard count <= 16*1024*1024 else { self.close(connection); return }
            let next = {
                self.send(Data(repeating: 0, count: 9), connection)
                self.readHeader(connection)
            }
            guard count > 0 else { next(); return }
            self.read(count, connection) { data in
                guard let frame = UIImage(data: data) else { self.close(connection); return }
                self.image = frame
                if !self.active { self.active = true; self.onConnection?(true) }
                next()
            }
        }
    }

    private func pointer(_ type: UInt8, _ touch: UITouch) {
        guard let frame = image, let connection = peer else { return }
        let scale = min(bounds.width/frame.size.width, bounds.height/frame.size.height)
        guard scale > 0 else { return }
        let width = frame.size.width * scale, height = frame.size.height * scale
        let point = touch.location(in: self)
        let x = (point.x - (bounds.width-width)/2)/width
        let y = (point.y - (bounds.height-height)/2)/height
        if type == 1 && !(0...1 ~= x && 0...1 ~= y) { return }
        if type == 1 { tracked = touch }
        guard touch === tracked else { return }
        var packet = Data([type])
        for coordinate in [x,y] {
            var value = Float(min(1,max(0,coordinate))).bitPattern.bigEndian
            withUnsafeBytes(of: &value) { packet.append(contentsOf: $0) }
        }
        send(packet, connection)
        if type == 3 { tracked = nil }
    }
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let touch = touches.first { pointer(1,touch) }
    }
    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let touch = tracked { pointer(2,touch) }
    }
    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let touch = tracked { pointer(3,touch) }
    }
    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        touchesEnded(touches, with: event)
    }
}
