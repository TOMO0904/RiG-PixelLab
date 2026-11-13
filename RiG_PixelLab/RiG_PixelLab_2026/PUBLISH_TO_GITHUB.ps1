# PUBLISH_TO_GITHUB.ps1
# Publishes ONLY to the verified GitHub user ID 184657574 / TOMO0904.
# The script will not modify any existing repository.
$ErrorActionPreference = 'Stop'
$expectedOwner = 'TOMO0904'
$expectedId = '184657574'
$repoName = 'RiG-PixelLab'
$fullName = "$expectedOwner/$repoName"
$root = $PSScriptRoot

function CheckExit([string]$action) {
    if ($LASTEXITCODE -ne 0) {
        throw "$action failed. Exit code: $LASTEXITCODE"
    }
}

try {
    Write-Host '==================================================' -ForegroundColor Cyan
    Write-Host 'RiG++ PixelLab - SAFE GitHub public release' -ForegroundColor Cyan
    Write-Host '==================================================' -ForegroundColor Cyan
    Write-Host "Target repository: $fullName" -ForegroundColor Yellow
    Write-Host 'Account verification: login AND numeric GitHub user ID'
    Write-Host ''
    if (-not (Test-Path (Join-Path $root 'README.md'))) {
        throw 'README.md is missing. Extract the whole ZIP first.'
    }
    if (Test-Path (Join-Path $root '.git')) {
        throw 'This folder already contains a .git repository. To avoid modifying an existing repository, extract a fresh ZIP and retry.'
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git is not installed. Install it using: winget install --id Git.Git --exact ; then open a new terminal and retry.'
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'GitHub CLI (gh) is not installed. Install it using: winget install --id GitHub.cli --exact ; then open a new terminal and retry.'
    }

    $savedAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & gh auth status --hostname github.com *> $null
        $authCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedAction
    }
    if ($authCode -ne 0) {
        Write-Host 'GitHub authentication required. A browser login will open.' -ForegroundColor Yellow
        & gh auth login --hostname github.com --git-protocol https --web
        CheckExit 'GitHub login'
    }

    $who = & gh api user | ConvertFrom-Json
    CheckExit 'GitHub identity lookup'
    Write-Host "Authenticated login: $($who.login)"
    Write-Host "Authenticated GitHub user ID: $($who.id)"
    if (($who.login -cne $expectedOwner) -or ([string]$who.id -cne $expectedId)) {
        throw "ACCOUNT MISMATCH. Login must be $expectedOwner and user ID must be $expectedId. Nothing was published."
    }
    Write-Host 'Account confirmed. Correct identity.' -ForegroundColor Green

    $repoNames = @(& gh repo list $expectedOwner --limit 1000 --json name --jq '.[].name')
    CheckExit 'Repository list'
    if ($repoNames -contains $repoName) {
        throw 'The target repository ALREADY EXISTS. To avoid overwriting anything, stopped without publishing.'
    }

    $allowed = @(
        '.gitignore','LICENSE','README.md','CHANGELOG.md','ARTICLE_GUIDE.md',
        'PHOTO_CREDITS.md','GITHUB_PUBLISH_README.md',
        'app.py','pixel_engine.py','cli.py','requirements.txt',
        'START_HERE_Windows.bat','RUN_TESTS_Windows.bat',
        'PUBLISH_TO_GITHUB.ps1','PUBLISH_TO_GITHUB_Windows.bat',
        'samples/sample_real_rocket.jpg',
        'examples/new_photo_3stages.png',
        'examples/game_background_rocket.png',
        'examples/sunset_background_rocket.png',
        'examples/night_background_rocket.png',
        'examples/game_demo_rocket.png',
        'tests/test_pixel_engine.py'
    )
    foreach ($f in $allowed) {
        if (-not (Test-Path (Join-Path $root $f))) {
            throw "A required publication file is missing: $f"
        }
    }
    Write-Host ''
    Write-Host "Publishing $($allowed.Count) approved source files and sample assets only." -ForegroundColor Yellow
    Write-Host 'Public repository: anyone will be able to download these files.' -ForegroundColor Yellow
    Write-Host 'No personal photos, virtual environments, or other local files will be staged.'
    $answer = Read-Host 'To create this PUBLIC repo, type TOMO0904/PUBLIC exactly'
    if ($answer -cne 'TOMO0904/PUBLIC') {
        throw 'Confirmation not matched. No changes made.'
    }

    Push-Location $root
    try {
        & git init --initial-branch=main
        CheckExit 'Git init'
        foreach ($f in $allowed) {
            & git add -- $f
            CheckExit "git add $f"
        }
        & git -c user.name='TOMO0904' -c user.email='184657574+TOMO0904@users.noreply.github.com' commit -m 'Initial release: RiG++ PixelLab v4'
        CheckExit 'Git commit'
        & gh auth setup-git
        CheckExit 'Git credential setup'
        & gh repo create $fullName --public --description 'RiG++ PixelLab: Convert real photos into pixel art and game-ready backgrounds (Windows/Python)' --source . --remote origin --push
        CheckExit 'GitHub public repository creation and push'
        & gh repo view $fullName --json url --jq .url
        CheckExit 'Publication verification'
        Write-Host ''
        Write-Host 'PUBLICATION COMPLETE' -ForegroundColor Green
        Write-Host "https://github.com/$fullName" -ForegroundColor Green
    } finally {
        Pop-Location
    }
} catch {
    Write-Host ''
    Write-Host "STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No existing GitHub repository was overwritten.' -ForegroundColor Yellow
    exit 1
}
