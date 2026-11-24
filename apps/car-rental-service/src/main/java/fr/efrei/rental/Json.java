package fr.efrei.rental;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Utilitaires JSON minimaux.
 */
final class Json {

    private Json() {
    }

    static String escape(String value) {
        StringBuilder out = new StringBuilder(value.length());
        for (char c : value.toCharArray()) {
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.toString();
    }

    static String array(List<Car> cars) {
        return cars.stream().map(Car::toJson).collect(Collectors.joining(",", "[", "]"));
    }
}
