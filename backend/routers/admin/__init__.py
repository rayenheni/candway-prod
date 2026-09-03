from fastapi import APIRouter

from backend.routers.admin.analytics import router as analytics_router
from backend.routers.admin.cms import router as cms_router
from backend.routers.admin.courses import router as courses_router
from backend.routers.admin.credits import router as credits_router
from backend.routers.admin.finance import router as finance_router
from backend.routers.admin.interviews import router as interviews_router
from backend.routers.admin.invoices import router as invoices_router
from backend.routers.admin.job_categories import router as job_categories_router
from backend.routers.admin.jobs import router as jobs_router
from backend.routers.admin.kyb import router as kyb_router
from backend.routers.admin.marketing import marketing_router
from backend.routers.admin.organizations import router as organizations_router
from backend.routers.admin.payments import router as payments_router
from backend.routers.admin.plans import router as plans_router
from backend.routers.admin.settings import settings_router
from backend.routers.admin.subscriptions import router as subscriptions_router
from backend.routers.admin.system import router as system_router
from backend.routers.admin.tickets import router as tickets_router
from backend.routers.admin.users import router as users_router
from backend.routers.admin.verifications import router as verifications_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(analytics_router)
router.include_router(cms_router)
router.include_router(courses_router)
router.include_router(credits_router)
router.include_router(finance_router)
router.include_router(interviews_router)
router.include_router(invoices_router)
router.include_router(jobs_router)
router.include_router(payments_router)
router.include_router(plans_router)
router.include_router(subscriptions_router)
router.include_router(system_router)
router.include_router(tickets_router)
router.include_router(users_router)
router.include_router(verifications_router)
router.include_router(marketing_router)
router.include_router(settings_router)
router.include_router(job_categories_router)
router.include_router(kyb_router)
router.include_router(organizations_router)
