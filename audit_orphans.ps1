# Forensic Orphan Detection Audit Script
$ErrorActionPreference = "SilentlyContinue"
$base = "C:\Users\rayen\projects\candway_landing_page (2)\masar_landing_page\masar_landing_page"
$report = @()

function Log($msg) { Write-Host $msg }
function Finding($cat, $item, $status, $evidence) {
    $line = "$cat|$item|$status|$evidence"
    $script:report += $line
    Log $line
}

# ============================================================
# SECTION 1: UNUSED ROUTES
# ============================================================
Log "=== SECTION 1: UNUSED ROUTES ==="

# Get all router files
$routerFiles = Get-ChildItem -Path "$base\backend\routers" -Recurse -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" -and $_.Name -notmatch "utils\.py$" }

foreach ($rf in $routerFiles) {
    $content = Get-Content $rf.FullName -Raw
    # Find all @router.xxx decorated functions
    $matches = [regex]::Matches($content, '@router\.(get|post|put|delete|patch)\s*\(\s*["\x27]([^"\x27]+)["\x27]')
    foreach ($m in $matches) {
        $method = $m.Groups[1].Value.ToUpper()
        $path = $m.Groups[2].Value
        $shortName = $rf.Name -replace '\.py$', ''
        
        # Check if this file is imported in __init__.py
        $initContent = Get-Content "$base\backend\routers\__init__.py" -Raw
        $imported = $initContent -match $shortName
        
        if (-not $imported) {
            # Also check if the module is imported elsewhere
            $searchResult = rg -l $shortName "$base\backend" --include "*.py" 2>$null
            $otherRefs = ($searchResult | Where-Object { $_ -ne $rf.FullName -and $_ -notmatch "__init__" }).Count
            if ($otherRefs -eq 0) {
                Finding "ROUTE" "$method $path" "UNUSED" "$($rf.FullName): @router.$($m.Groups[1].Value)('$path') -- file not imported in __init__.py and no references found"
            }
        }
    }
}

# Check pages.py for orphan routes (it renders HTML pages, not API)
$pagesContent = Get-Content "$base\backend\routers\pages.py" -Raw
$pageMatches = [regex]::Matches($pagesContent, '@router\.(get|post|put|delete|patch)\s*\(\s*["\x27]([^"\x27]+)["\x27]')
Log "Pages router has $($pageMatches.Count) routes"

# Check admin __init__.py
$adminInit = Get-Content "$base\backend\routers\admin\__init__.py" -Raw
Log "Admin __init__.py content:"
Log $adminInit

# Check candidate __init__.py
$candidateInit = Get-Content "$base\backend\routers\candidate\__init__.py" -Raw
Log "Candidate __init__.py content:"
Log $candidateInit

# Check ai_interview __init__.py
$aiInterviewInit = Get-Content "$base\backend\routers\ai_interview\__init__.py" -Raw
Log "AI Interview __init__.py content:"
Log $aiInterviewInit

# ============================================================
# SECTION 2: UNUSED MODELS
# ============================================================
Log "`n=== SECTION 2: UNUSED MODELS ==="

# Extract all model class names from models/__init__.py
$modelsInit = Get-Content "$base\backend\models\__init__.py" -Raw
$allModelClasses = @(
    # Foundation
    "User", "AuditLog", "ConsentLog", "EmailVerification", "FeatureFlag",
    "LoginAttempt", "Notification", "PasswordReset", "ProfileVisit",
    "TokenBlacklist", "UndoAction", "Company", "CompanyMember", "CompanyVerification",
    "Category", "SubscriptionPlan", "PageSection", "SupportTicket", "SystemConfig",
    "SystemPrompt", "Ticket", "TranslationCache", "Announcement", "BlogPost",
    "DailyPlatformReport", "Opportunity", "SalesCampaign", "SalesLead",
    # Evaluation
    "ABExperiment", "ABTestAssignment", "ABTestExperiment", "AIAuditLog",
    "CalibrationSample", "DBTestResult", "DriftSnapshot", "InterviewTurn",
    "PromptTest", "PromptVariant", "ScoringVariantResult", "SkillDefinition",
    "Rubric", "RubricScoringDetail", "RubricSnapshot", "Verdict",
    "EvaluationResult", "EvaluationSession", "EntryPoint", "EvaluationConfigSnapshot",
    "ResolvedEvaluationConfig", "AdminProfile", "CandidateProfile", "RecruiterProfile",
    # Core
    "BatchJob", "PipelineAutomationRule", "PipelineStage", "ChatbotLead",
    "InterviewQuestion", "Job", "SavedJob", "JobAIConfig", "JobCategory",
    "JobEvaluationFramework", "JobNiceToHave", "JobPipelineStage", "JobRoleOverview",
    "JobScreeningQuestion", "JobSkill", "CareerRoadmap", "Coupon", "Course",
    "CourseReview", "Enrollment", "Lesson", "LessonProgress", "PayoutRequest",
    "Question", "Quiz", "Section",
    # ATS
    "Application", "CvDocument", "EEOConsent", "ExtractedSkill", "Qualification",
    "Candidate", "TalentPool", "TalentPoolCandidate",
    "Interview", "InterviewFeedback", "InterviewParticipant", "InterviewScorecard",
    "ScorecardSubmission", "ActivityLog", "ApplicationStageHistory",
    "CandidateInteraction", "CandidateRating", "Comment", "TaggedNote", "TeamMember",
    "BackgroundCheck", "BackgroundCheckStatusLog", "Offer", "OfferTemplate",
    "BotIntegration", "CampaignTemplate", "EmailSequenceLog", "EmailTemplate",
    "ReEngagementCampaign", "ReEngagementCandidate", "WebhookIntegration",
    "Conversation", "ConversationParticipant", "Message",
    # Finance
    "CampaignCost", "Invoice", "ReportSnapshot", "SavedReport", "Transaction"
)

foreach ($model in $allModelClasses) {
    # Search in backend/ excluding models/ and __init__.py files
    $refs = rg -l "\b$model\b" "$base\backend" --include "*.py" 2>$null | Where-Object { $_ -notmatch "\\models\\" -and $_ -notmatch "__init__\.py$" }
    $migRefs = rg -l "\b$model\b" "$base\alembic" --include "*.py" 2>$null
    
    $routerRefs = ($refs | Where-Object { $_ -match "\\routers\\" }).Count
    $serviceRefs = ($refs | Where-Object { $_ -match "\\services\\" }).Count
    $jobRefs = ($refs | Where-Object { $_ -match "\\jobs\\" }).Count
    $aiRefs = ($refs | Where-Object { $_ -match "\\ai\\" }).Count
    $totalNonModelRefs = $refs.Count
    
    if ($totalNonModelRefs -eq 0 -and $migRefs.Count -eq 0) {
        Finding "MODEL" $model "UNUSED" "No references outside models/ or alembic/"
    } elseif ($totalNonModelRefs -eq 0 -and $migRefs.Count -gt 0) {
        Finding "MODEL" $model "MIGRATION-ONLY" "Only referenced in alembic migrations ($($migRefs.Count) files)"
    }
}

# ============================================================
# SECTION 3: UNUSED SERVICES
# ============================================================
Log "`n=== SECTION 3: UNUSED SERVICES ==="

# backend/services/
$serviceFiles = Get-ChildItem "$base\backend\services" -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" }
foreach ($sf in $serviceFiles) {
    $moduleName = $sf.BaseName
    $refs = rg -l $moduleName "$base\backend" --include "*.py" 2>$null | Where-Object { $_ -ne $sf.FullName }
    if ($refs.Count -eq 0) {
        Finding "SERVICE" $moduleName "UNUSED" "No references in backend/ outside itself"
    } else {
        Log "  SERVICE $moduleName: USED ($($refs.Count) references)"
    }
}

# backend/repository/
$repoFiles = Get-ChildItem "$base\backend\repository" -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" -and $_.Name -notmatch "^_" }
foreach ($rf in $repoFiles) {
    $moduleName = $rf.BaseName
    $refs = rg -l $moduleName "$base\backend" --include "*.py" 2>$null | Where-Object { $_ -ne $rf.FullName }
    if ($refs.Count -eq 0) {
        Finding "REPOSITORY" $moduleName "UNUSED" "No references in backend/ outside itself"
    } else {
        Log "  REPOSITORY $moduleName: USED ($($refs.Count) references)"
    }
}

# backend/utils/
$utilFiles = Get-ChildItem "$base\backend\utils" -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" }
foreach ($uf in $utilFiles) {
    $moduleName = $uf.BaseName
    $refs = rg -l $moduleName "$base\backend" --include "*.py" 2>$null | Where-Object { $_ -ne $uf.FullName }
    if ($refs.Count -eq 0) {
        Finding "UTILITY" $moduleName "UNUSED" "No references in backend/ outside itself"
    } else {
        Log "  UTILITY $moduleName: USED ($($refs.Count) references)"
    }
}

# ============================================================
# SECTION 4: UNUSED JAVASCRIPT
# ============================================================
Log "`n=== SECTION 4: UNUSED JAVASCRIPT ==="

$jsFiles = Get-ChildItem "$base\js" -Recurse -Filter "*.js"
$htmlFiles = Get-ChildItem "$base" -Recurse -Filter "*.html"
$htmlContent = ""
foreach ($h in $htmlFiles) {
    $htmlContent += (Get-Content $h.FullName -Raw) + "`n"
}

foreach ($jsf in $jsFiles) {
    $jsName = $jsf.Name
    $shortJsName = $jsf.Name -replace '\.js$', ''
    
    # Check if referenced in HTML (script src, import, fetch)
    if ($htmlContent -match [regex]::Escape($jsName)) {
        Log "  JS $jsName: USED"
    } elseif ($htmlContent -match $shortJsName) {
        Log "  JS $jsName: USED (partial name match)"
    } else {
        # Also check if other JS files import/reference it
        $jsRefs = rg -l $shortJsName "$base\js" --include "*.js" 2>$null | Where-Object { $_ -ne $jsf.FullName }
        $htmlRefs = rg -l $shortJsName "$base\pages" --include "*.html" 2>$null
        $rootHtmlRefs = rg -l $shortJsName "$base" --include "*.html" 2>$null
        $allHtmlRefs = $htmlRefs + $rootHtmlRefs | Select-Object -Unique
        
        if ($allHtmlRefs.Count -eq 0 -and $jsRefs.Count -eq 0) {
            Finding "JS" $jsName "UNUSED" "Not referenced in any HTML or other JS file"
        } else {
            Log "  JS $jsName: USED via other references"
        }
    }
}

# ============================================================
# SECTION 5: UNUSED CSS
# ============================================================
Log "`n=== SECTION 5: UNUSED CSS ==="

$cssFiles = Get-ChildItem "$base\css" -Filter "*.css"
foreach ($csf in $cssFiles) {
    $cssName = $csf.Name
    if ($htmlContent -match [regex]::Escape($cssName)) {
        Log "  CSS $cssName: USED"
    } else {
        # Check for @import in CSS files
        $cssAllContent = ""
        foreach ($otherCsf in $cssFiles) {
            $cssAllContent += (Get-Content $otherCsf.FullName -Raw) + "`n"
        }
        if ($cssAllContent -match $cssName) {
            Log "  CSS $cssName: USED (imported by another CSS)"
        } else {
            Finding "CSS" $cssName "UNUSED" "Not referenced in any HTML or CSS file"
        }
    }
}

# ============================================================
# SECTION 6: UNUSED ENV VARS
# ============================================================
Log "`n=== SECTION 6: UNUSED ENV VARS ==="

$envContent = Get-Content "$base\.env.example" -Raw
$envVars = [regex]::Matches($envContent, '^([A-Z_][A-Z0-9_]*)=', [System.Text.RegularExpressions.RegexOptions]::Multiline)
$backendContent = ""
$pyFiles = Get-ChildItem "$base\backend" -Recurse -Filter "*.py"
foreach ($py in $pyFiles) {
    $backendContent += (Get-Content $py.FullName -Raw) + "`n"
}

foreach ($ev in $envVars) {
    $varName = $ev.Groups[1].Value
    if ($backendContent -match $varName) {
        Log "  ENV $varName: USED"
    } else {
        Finding "ENV" $varName "UNUSED" "Not referenced in any backend Python file"
    }
}

# ============================================================
# SECTION 7: UNUSED REDIS KEYS
# ============================================================
Log "`n=== SECTION 7: UNUSED REDIS KEYS ==="

$redisRefs = rg -n "redis\.(set|get|hset|hget|delete|expire|exists|incr|decr|lpush|rpush|lrange|smembers|sadd|srem|zadd|zrange)" "$base\backend" --include "*.py" 2>$null
if ($redisRefs) {
    foreach ($rr in $redisRefs) {
        Log "  REDIS: $rr"
    }
} else {
    Log "  No redis operations found in backend/"
}

# ============================================================
# SECTION 8: SCHEDULED JOBS CHECK
# ============================================================
Log "`n=== SECTION 8: SCHEDULED JOBS ==="

$schedulerFile = "$base\backend\routers\scheduler.py"
if (Test-Path $schedulerFile) {
    $schedContent = Get-Content $schedulerFile -Raw
    $jobMatches = [regex]::Matches($schedContent, 'add_job\s*\(\s*([^,\)]+)')
    foreach ($jm in $jobMatches) {
        $funcName = $jm.Groups[1].Value.Trim().Trim('"', "'")
        $funcRefs = rg -l "def\s+$funcName" "$base\backend" --include "*.py" 2>$null
        if ($funcRefs.Count -eq 0) {
            Finding "SCHEDJOB" $funcName "DEAD" "Function not defined anywhere"
        } else {
            Log "  SCHEDJOB $funcName: EXISTS at $($funcRefs[0])"
        }
    }
} else {
    Log "  scheduler.py not found, checking for scheduling elsewhere"
    $schedRefs = rg -l "add_job|schedule|crontab|APScheduler" "$base\backend" --include "*.py" 2>$null
    foreach ($sr in $schedRefs) {
        Log "  SCHEDULER ref: $sr"
    }
}

# ============================================================
# OUTPUT
# ============================================================
Log "`n=== SUMMARY ==="
$findings = $report | Where-Object { $_ -match "\|UNUSED\|\|UNUSED\||DEAD\|MIGRATION-ONLY" }
Log "Total orphan findings: $($findings.Count)"
Log "Total items checked: $($report.Count)"
