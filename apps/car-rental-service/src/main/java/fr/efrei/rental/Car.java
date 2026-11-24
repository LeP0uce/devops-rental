package fr.efrei.rental;

/**
 * Véhicule proposé à la location.
 */
public record Car(String id, String brand, String model, String category, boolean available) {

    /**
     * Sérialise le véhicule en JSON sans dépendance externe.
     */
    public String toJson() {
        return "{"
                + "\"id\":\"" + Json.escape(id) + "\","
                + "\"brand\":\"" + Json.escape(brand) + "\","
                + "\"model\":\"" + Json.escape(model) + "\","
                + "\"category\":\"" + Json.escape(category) + "\","
                + "\"available\":" + available
                + "}";
    }
}
