package fr.efrei.rental;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CarRentalApplicationTest {

    private final HttpClient client = HttpClient.newHttpClient();
    private CarRentalApplication app;

    @BeforeEach
    void startServer() throws IOException {
        app = new CarRentalApplication(0, CarRepository.withDefaultFleet());
        app.start();
    }

    @AfterEach
    void stopServer() {
        app.stop();
    }

    private HttpResponse<String> get(String path) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + app.port() + path)).build();
        return client.send(request, HttpResponse.BodyHandlers.ofString());
    }

    @Test
    void healthEndpointReportsUp() throws Exception {
        HttpResponse<String> response = get("/health");
        assertEquals(200, response.statusCode());
        assertEquals("{\"status\":\"UP\"}", response.body());
    }

    @Test
    void carsEndpointListsFleet() throws Exception {
        HttpResponse<String> response = get("/cars");
        assertEquals(200, response.statusCode());
        assertTrue(response.body().contains("\"id\":\"c1\""));
        assertTrue(response.body().contains("\"id\":\"c4\""));
    }

    @Test
    void carsEndpointFiltersAvailableCars() throws Exception {
        HttpResponse<String> response = get("/cars?available=true");
        assertEquals(200, response.statusCode());
        assertTrue(!response.body().contains("\"id\":\"c3\""));
    }

    @Test
    void unknownCarReturns404() throws Exception {
        assertEquals(404, get("/cars/nope").statusCode());
    }
}
