# app/routes.py

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.schemas import OrgCreate, OrgOut, AdminLogin, OrgUpdate
from app import crud, auth

router = APIRouter()
bearer_scheme = HTTPBearer()  # this shows a simple "Authorization: Bearer <token>" UI


def verify_token_and_admin_token_string(token_str: str):
    payload = auth.decode_token(token_str)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def verify_token_and_admin(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """
    Dependency that extracts token string from HTTPAuthorizationCredentials and verifies it.
    Use this as `Depends(verify_token_and_admin)` in protected endpoints.
    """
    token = creds.credentials  # this is the raw JWT string (no "Bearer " prefix)
    return verify_token_and_admin_token_string(token)


@router.post("/org/create", response_model=OrgOut)
async def create_org(payload: OrgCreate):
    try:
        res = await crud.create_organization(payload.organization_name, payload.email, payload.password)
        return {
            "organization_name": res["organization_name"],
            "collection_name": res["collection_name"],
            "admin_email": res["admin_email"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/org/get", response_model=OrgOut)
async def get_org(organization_name: str):
    doc = await crud.get_organization(organization_name)
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "organization_name": doc["organization_name"],
        "collection_name": doc["collection_name"],
        "admin_email": doc["admin"]["email"]
    }


@router.put("/org/update")
async def update_org(payload: OrgUpdate, token_payload: dict = Depends(verify_token_and_admin)):
    # token_payload contains the decoded JWT claims (e.g., sub, org_id)
    try:
        await crud.update_organization(
            payload.organization_name,
            payload.new_organization_name,
            payload.email,
            payload.password
        )
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/org/delete")
async def delete_org(organization_name: str, token_payload: dict = Depends(verify_token_and_admin)):
    success = await crud.delete_organization(organization_name)
    if not success:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"success": True}


@router.post("/admin/login")
async def admin_login(payload: AdminLogin):
    authres = await crud.admin_authenticate(payload.email, payload.password)
    if not authres:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_access_token({"sub": authres["admin_email"], "org_id": authres["org_id"]})
    return {"access_token": token, "token_type": "bearer"}
