FROM eclipse-temurin:21-jdk-noble@sha256:dc333cdac241f073941f043792f2a2f9b790bfe7cd98ef2843c08880986708de AS build
WORKDIR /workspace
COPY gradlew settings.gradle.kts build.gradle.kts ./
COPY gradle ./gradle
RUN ./gradlew --no-daemon --version
COPY src ./src
RUN ./gradlew --no-daemon jar

FROM eclipse-temurin:21-jre-noble@sha256:54999a956a8bf8be9af0052790a6a832bf91a62fad3199fd194c3cc28057fc62
WORKDIR /app
RUN useradd --system --uid 10001 rental
COPY --from=build /workspace/build/libs/car-rental-service.jar ./car-rental-service.jar
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/car-rental-service.jar"]
