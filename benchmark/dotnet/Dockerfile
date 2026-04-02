# Stage 1 — Build
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

COPY McpBenchmarkServer/McpBenchmarkServer.csproj McpBenchmarkServer/
RUN dotnet restore McpBenchmarkServer/McpBenchmarkServer.csproj

COPY . .
RUN dotnet publish McpBenchmarkServer/McpBenchmarkServer.csproj \
    -c Release \
    -o /app/publish \
    --no-restore

# Stage 2 — Runtime
FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app

COPY --from=build /app/publish .

EXPOSE 8003

ENV ASPNETCORE_URLS=http://+:8003
ENV PORT=8003

HEALTHCHECK --interval=5s --timeout=3s --retries=6 \
    CMD curl -f http://localhost:8003/health || exit 1

ENTRYPOINT ["dotnet", "McpBenchmarkServer.dll"]
