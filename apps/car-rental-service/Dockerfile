FROM eclipse-temurin:21-jdk-noble AS build
WORKDIR /workspace
COPY gradlew settings.gradle.kts build.gradle.kts ./
COPY gradle ./gradle
RUN ./gradlew --no-daemon --version
COPY src ./src
RUN ./gradlew --no-daemon jar

FROM eclipse-temurin:21-jre-noble
WORKDIR /app
RUN useradd --system --uid 10001 rental
COPY --from=build /workspace/build/libs/car-rental-service.jar ./car-rental-service.jar
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/car-rental-service.jar"]
