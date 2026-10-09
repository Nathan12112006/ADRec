param(
    [int[]]$Users = @(10, 100, 500),
    [int]$Repetitions = 1,
    [int]$WarmupSeconds = 1,
    [int]$MeasurementSeconds = 3,
    [int]$DrainSeconds = 10,
    [int]$SpawnRate = 100,
    [string]$LocustImage = "adflow-locust:2.46.7",
    [string]$FlatIndexPath = "/artifacts/ticket49-flat",
    [string]$HnswIndexPath = "/artifacts/ticket49-hnsw",
    [switch]$ResetFromTemplate,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$backendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repositoryRoot = (Resolve-Path (Join-Path $backendRoot "..")).Path
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"
$benchmarkUrl = "postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_benchmark"
$templateUrl = "postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_benchmark_template"
$loadgenUrl = "postgresql+psycopg://adflow:adflow@postgres:5432/adflow_benchmark"
$composeUrl = "postgresql+psycopg://adflow:adflow@postgres:5432/adflow_benchmark"
$redisEnabled = "redis://redis:6379/0"

if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found: $python"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repositoryRoot "artifacts\benchmarks\ticket49-matrix-smokes"
}
if (-not (Test-Path (Join-Path $backendRoot "Dockerfile.locust"))) {
    throw "Pinned Locust image definition is missing."
}

docker image inspect $LocustImage *> $null
if ($LASTEXITCODE -ne 0) {
    docker build -f (Join-Path $backendRoot "Dockerfile.locust") -t $LocustImage $backendRoot
    if ($LASTEXITCODE -ne 0) { throw "Locust image build failed." }
}

$variants = @(
    @{ retrieval = "full_scan"; index = "" },
    @{ retrieval = "flat"; index = $FlatIndexPath },
    @{ retrieval = "hnsw"; index = $HnswIndexPath }
)
$cacheModes = @(
    @{ cache = "disabled"; redis = "disabled" },
    @{ cache = "enabled"; redis = $redisEnabled }
)

foreach ($variant in $variants) {
    foreach ($cacheMode in $cacheModes) {
        $env:ADFLOW_BENCHMARK_DATABASE_URL = $composeUrl
        $env:ADFLOW_REDIS_URL = $cacheMode.redis
        $env:ADFLOW_RETRIEVAL_INDEX_PATH = $variant.index

        docker compose --profile benchmark up -d --no-deps --force-recreate benchmark-api
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not start $($variant.retrieval)/$($cacheMode.cache); continuing."
            continue
        }

        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            $health = docker inspect adflow-benchmark-api --format '{{.State.Health.Status}}' 2>$null
            if ($LASTEXITCODE -eq 0 -and $health -eq "healthy") {
                $ready = $true
                break
            }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) {
            Write-Warning "Benchmark API did not become healthy for $($variant.retrieval)/$($cacheMode.cache); continuing."
            continue
        }

        $profiles = @(
            @{ name = "uniform-warm"; selection = "uniform"; cacheState = "warm" }
        )
        if ($cacheMode.cache -eq "enabled") {
            $profiles += @{ name = "hot-cold"; selection = "hot"; cacheState = "cold" }
        } else {
            $profiles += @{ name = "hot-no-cache"; selection = "hot"; cacheState = "warm" }
        }

        foreach ($workload in @("recommendation_only", "lifecycle")) {
            foreach ($profile in $profiles) {
                $matrixName = "$($variant.retrieval)-$($cacheMode.cache)-$workload-$($profile.name)"
                $matrixRoot = Join-Path $OutputRoot $matrixName
                if ($ResetFromTemplate) {
                    docker compose --profile benchmark stop benchmark-api
                    if ($LASTEXITCODE -ne 0) {
                        Write-Warning "Could not stop benchmark API before cloning for $matrixName; continuing."
                        continue
                    }
                    & $python (Join-Path $backendRoot "scripts\reset_benchmark_database.py") `
                        --database-url $benchmarkUrl `
                        --application-database-url "postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow" `
                        --template-database-url $templateUrl `
                        --confirm-database adflow_benchmark
                    if ($LASTEXITCODE -ne 0) {
                        Write-Warning "Could not clone the clean benchmark baseline for $matrixName; continuing."
                        continue
                    }
                }
                docker compose --profile benchmark up -d --no-deps --force-recreate benchmark-api
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Could not restart benchmark API for $matrixName; continuing."
                    continue
                }
                $ready = $false
                for ($attempt = 0; $attempt -lt 30; $attempt++) {
                    $health = docker inspect adflow-benchmark-api --format '{{.State.Health.Status}}' 2>$null
                    if ($LASTEXITCODE -eq 0 -and $health -eq "healthy") {
                        $ready = $true
                        break
                    }
                    Start-Sleep -Seconds 2
                }
                if (-not $ready) {
                    Write-Warning "Benchmark API did not recover for $matrixName; continuing."
                    continue
                }
                $arguments = @(
                    (Join-Path $backendRoot "scripts\benchmark_runner.py"),
                    "--host", "http://127.0.0.1:18001",
                    "--profile-database-url", $benchmarkUrl,
                    "--locust-image", $LocustImage,
                    "--loadgen-database-url", $loadgenUrl,
                    "--loadgen-host", "http://127.0.0.1:8000",
                    "--workload", $workload,
                    "--users"
                )
                $arguments += $Users | ForEach-Object { [string]$_ }
                $arguments += @(
                    "--repetitions", [string]$Repetitions,
                    "--spawn-rate", [string]$SpawnRate,
                    "--warmup-seconds", [string]$WarmupSeconds,
                    "--measurement-seconds", [string]$MeasurementSeconds,
                    "--drain-seconds", [string]$DrainSeconds,
                    "--user-selection", $profile.selection,
                    "--cache-state", $profile.cacheState,
                    "--output-root", $matrixRoot
                )
                Write-Host "Running $matrixName for users $($Users -join ', ')"
                & $python @arguments
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "$matrixName contains an incomplete run; raw artifacts were retained."
                }
                Start-Sleep -Seconds 5
                $runDirectory = $null
                if (Test-Path $matrixRoot) {
                    $runDirectory = Get-ChildItem $matrixRoot -Directory |
                        Sort-Object LastWriteTime -Descending |
                        Select-Object -First 1
                }
                if (
                    $runDirectory -and
                    (Test-Path (Join-Path $runDirectory.FullName "matrix.json")) -and
                    -not (Test-Path (Join-Path $runDirectory.FullName "preflight_failure.json"))
                ) {
                    & $python (Join-Path $backendRoot "scripts\report_benchmarks.py") $runDirectory.FullName
                }
            }
        }
    }
}

$env:ADFLOW_REDIS_URL = $redisEnabled
$env:ADFLOW_RETRIEVAL_INDEX_PATH = ""
$env:ADFLOW_BENCHMARK_DATABASE_URL = $composeUrl
docker compose --profile benchmark up -d --no-deps --force-recreate benchmark-api
