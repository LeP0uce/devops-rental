package fr.efrei.rental;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class CarRepositoryTest {

    private final CarRepository repository = CarRepository.withDefaultFleet();

    @Test
    void defaultFleetContainsFourCars() {
        assertEquals(4, repository.findAll().size());
    }

    @Test
    void availableCarsExcludeRentedOnes() {
        assertEquals(3, repository.findAvailable().size());
        assertTrue(repository.findAvailable().stream().allMatch(Car::available));
    }

    @Test
    void findByIdReturnsMatchingCar() {
        assertEquals("Peugeot", repository.findById("c2").orElseThrow().brand());
    }

    @Test
    void findByIdReturnsEmptyForUnknownCar() {
        assertFalse(repository.findById("unknown").isPresent());
    }

    @Test
    void toJsonEscapesSpecialCharacters() {
        Car car = new Car("x\"1", "Br\\and", "M", "standard", true);
        assertEquals(
                "{\"id\":\"x\\\"1\",\"brand\":\"Br\\\\and\",\"model\":\"M\",\"category\":\"standard\",\"available\":true}",
                car.toJson());
    }
}
