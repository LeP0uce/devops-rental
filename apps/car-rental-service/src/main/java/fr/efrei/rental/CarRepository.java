package fr.efrei.rental;

import java.util.List;
import java.util.Optional;

/**
 * Catalogue en mémoire des véhicules.
 */
public class CarRepository {

    private final List<Car> cars;

    public CarRepository(List<Car> cars) {
        this.cars = List.copyOf(cars);
    }

    public static CarRepository withDefaultFleet() {
        return new CarRepository(List.of(
                new Car("c1", "Renault", "Clio", "economy", true),
                new Car("c2", "Peugeot", "308", "standard", true),
                new Car("c3", "Tesla", "Model 3", "premium", false),
                new Car("c4", "Toyota", "Corolla", "standard", true)));
    }

    public List<Car> findAll() {
        return cars;
    }

    public List<Car> findAvailable() {
        return cars.stream().filter(Car::available).toList();
    }

    public Optional<Car> findById(String id) {
        return cars.stream().filter(car -> car.id().equals(id)).findFirst();
    }
}
