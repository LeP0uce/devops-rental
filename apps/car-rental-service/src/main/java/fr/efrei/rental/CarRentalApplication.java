package fr.efrei.rental;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

/**
 * Service HTTP de location : expose la santé du service et le catalogue.
 */
public final class CarRentalApplication {

    private final HttpServer server;

    public CarRentalApplication(int port, CarRepository repository) throws IOException {
        server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/health", exchange -> respond(exchange, 200, "{\"status\":\"UP\"}"));
        server.createContext("/cars", exchange -> handleCars(exchange, repository));
    }

    public void start() {
        server.start();
    }

    public void stop() {
        server.stop(0);
    }

    public int port() {
        return server.getAddress().getPort();
    }

    private static void handleCars(HttpExchange exchange, CarRepository repository) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            respond(exchange, 405, "{\"error\":\"method not allowed\"}");
            return;
        }
        String path = exchange.getRequestURI().getPath();
        if ("/cars".equals(path) || "/cars/".equals(path)) {
            String query = Optional.ofNullable(exchange.getRequestURI().getQuery()).orElse("");
            boolean onlyAvailable = query.contains("available=true");
            var cars = onlyAvailable ? repository.findAvailable() : repository.findAll();
            respond(exchange, 200, Json.array(cars));
            return;
        }
        String id = path.substring("/cars/".length());
        Optional<Car> car = repository.findById(id);
        if (car.isPresent()) {
            respond(exchange, 200, car.get().toJson());
        } else {
            respond(exchange, 404, "{\"error\":\"car not found\"}");
        }
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
        CarRentalApplication app = new CarRentalApplication(port, CarRepository.withDefaultFleet());
        app.start();
        System.out.println("car-rental-service listening on port " + app.port());
    }
}
