# -*- coding: utf-8 -*-
"""
main.py – FastAPI server for Twilio WhatsApp integration.
Vayu orchestrator = root entry point.
Decides whether to stay in Vayu or hand off to Karna.
"""
# ✅ Load environment


import os
import asyncio
import logging
import async_timeout
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from fastapi.concurrency import run_in_threadpool

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=dotenv_path)
#print("[DEBUG] Env loaded from", dotenv_path)

from vayu.karna.jobs import karna_jobs as karna_jobs
from pydantic import BaseModel
from vayu.karna.tools.airtable_utils import create_job_record, update_job_status



# ✅ Imports
from vayu.flows.orchestrator import vayu_orchestrator
from vayu.karna.tools.airtable_utils import get_client_id_from_phone, get_client_config

# ✅ FastAPI app
app = FastAPI(title="VayuBots API", version="1.0")
logger = logging.getLogger("vayu.whatsapp")
logger.setLevel(logging.INFO)


def _twiml(message: str) -> PlainTextResponse:
    """Helper to wrap a text reply as Twilio XML."""
    tw = MessagingResponse()
    tw.message(message)
    return PlainTextResponse(str(tw), media_type="application/xml")


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    """Main WhatsApp webhook for Twilio."""
    user_id = From.replace("whatsapp:", "")
    text = Body.strip() if Body else ""
    image_url = MediaUrl0 if int(NumMedia or 0) > 0 else None

    logger.info(f"[IN] From={user_id}, Text='{text[:60]}', Media={bool(image_url)}")

    try:
        # Step 1: Lookup client_id from Airtable
        client_id = await run_in_threadpool(get_client_id_from_phone, user_id)
        if not client_id:
            return _twiml("⚠️ Sorry, your number is not linked to a client in Airtable.")

        # Step 2: Fetch config
        client_config = await run_in_threadpool(get_client_config, client_id)
        user_name = client_config.get("name") or "Client"

        # Step 3: Call orchestrator with timeout
        async with async_timeout.timeout(20):
            response_text = await run_in_threadpool(
                vayu_orchestrator, client_id, user_name, text, image_url
            )

        return _twiml(response_text or "🤔 No response from orchestrator.")

    except asyncio.TimeoutError:
        logger.warning(f"[TIMEOUT] {user_id}")
        return _twiml("⌛ Sorry, the agent took too long to respond. Please try again.")
    except Exception as e:
        logger.exception(f"[ERROR] WhatsApp handler: {e}")
        return _twiml("⚠️ Internal server error. Please try again later.")


@app.get("/")
async def root():
    return {"status": "Vayu orchestrator webhook running"}

##############################
# Web endpoints
#####################################
# ----------------------------------------------
# Request Models
# ----------------------------------------------

class FullWorkflowRequest(BaseModel):
    client_id: str
    num_ideas: int = 20
    num_posts: int = 3

class CurateAllRequest(BaseModel):
    pass

class FullWorkflowAllRequest(BaseModel):
    num_ideas: int = 20
    num_posts: int = 3

class ClientInputRequest(BaseModel):
    client_id: str
    idea_text: str
    image_url: str | None = None
    channel: str = "Facebook"


# ----------------------------------------------
# SYNC endpoints (for short runs)
# ----------------------------------------------

@app.post("/api/karna/full_workflow")
def api_full_workflow(req: FullWorkflowRequest):
    """Runs full workflow for one client (waits until done)."""
    result = karna_jobs.full_workflow_one(req.client_id, req.num_ideas, req.num_posts)
    return {"status": "ok", "result": result}


@app.post("/api/karna/client_input")
def api_client_input(req: ClientInputRequest):
    """Submit new client idea via Make / Softr form."""
    result = karna_jobs.submit_client_input_job(req.client_id, req.idea_text, req.image_url, req.channel)
    return {"status": "ok", "result": result}


# ----------------------------------------------
# ASYNC endpoints (for long or multi-client runs)
# ----------------------------------------------

@app.post("/api/karna/full_workflow_async")
def api_full_workflow_async(req: FullWorkflowRequest, background: BackgroundTasks):
    """Queue full workflow for one client (logged in Airtable Jobs)."""
    job_id = create_job_record(client_id=req.client_id, job_type="full_workflow")

    def runner():
        update_job_status(job_id, "Running")
        try:
            result = karna_jobs.full_workflow_one(req.client_id, req.num_ideas, req.num_posts)
            update_job_status(job_id, "Completed", result_summary=result)
        except Exception as e:
            update_job_status(job_id, "Failed", error=e)

    background.add_task(runner)
    return {"status": "queued", "job_id": job_id, "client_id": req.client_id}


@app.post("/api/karna/full_workflow_all_async")
def api_full_workflow_all_async(req: FullWorkflowAllRequest, background: BackgroundTasks):
    """Queue full workflow for all clients (logged in Airtable Jobs)."""
    job_id = create_job_record(job_type="full_workflow_all")

    def runner():
        update_job_status(job_id, "Running")
        try:
            result = karna_jobs.full_workflow_all(req.num_ideas, req.num_posts)
            update_job_status(job_id, "Completed", result_summary=result)
        except Exception as e:
            update_job_status(job_id, "Failed", error=e)

    background.add_task(runner)
    return {"status": "queued", "job_id": job_id, "clients": "all"}

# ==============================================================
# 🌍 CREATE POSTS FOR ALL CLIENTS (ASYNC)
# ==============================================================

from pydantic import BaseModel

class CreatePostsAllRequest(BaseModel):
    num_posts: int = 3
    max_clients: int | None = None

class PublishAllRequest(BaseModel):
    max_clients: int | None = None
    
    
@app.post("/api/karna/create_posts_all_async")
def api_create_posts_all_async(req: CreatePostsAllRequest, background: BackgroundTasks):
    """Queues post creation for all active clients."""
    background.add_task(
        karna_jobs.create_posts_all,
        req.max_clients,
        req.num_posts
    )
    return {"status": "queued", "clients": "all", "num_posts": req.num_posts}

# ==============================================================
# 🌍 PUBLISH FOR ALL CLIENTS (ASYNC)
# ==============================================================
@app.post("/api/karna/publish_all_async")
def api_publish_all_async(req: PublishAllRequest, background: BackgroundTasks):
    """Queues publishing for all active clients."""
    background.add_task(
        karna_jobs.publish_all,  # or karna_jobs.publish_all if you make one
        req.max_clients
    )
    return {"status": "queued", "clients": "all"}



@app.post("/api/karna/curate_all_async")
def api_curate_all_async(req: CurateAllRequest, background: BackgroundTasks):
    """Queue idea curation for all clients (logged in Airtable Jobs)."""
    job_id = create_job_record(job_type="curate_all")

    def runner():
        update_job_status(job_id, "Running")
        try:
            result = karna_jobs.curate_all()
            update_job_status(job_id, "Completed", result_summary=result)
        except Exception as e:
            update_job_status(job_id, "Failed", error=e)

    background.add_task(runner)
    return {"status": "queued", "job_id": job_id, "clients": "all"}

# ------------------------------------------------------------
#  CREATE POSTS JOB (curation + post creation only)
# ------------------------------------------------------------
class CreatePostsRequest(BaseModel):
    client_id: str
    num_ideas: int = 10
    num_posts: int = 3

@app.post("/api/karna/create_posts_async")
def api_create_posts_async(req: CreatePostsRequest, background: BackgroundTasks):
    """Queues idea curation + post creation for a client."""
    background.add_task(karna_jobs.create_posts_job, req.client_id, req.num_ideas, req.num_posts)
    return {"status": "queued", "client_id": req.client_id}


# ------------------------------------------------------------
#  PUBLISH JOB (publishing only)
# ------------------------------------------------------------
@app.post("/api/karna/publish_async")
def api_publish_async(client_id: str, background: BackgroundTasks):
    """Queues publishing job for a client."""
    background.add_task(karna_jobs.publish_job, client_id)
    return {"status": "queued", "client_id": client_id}


    
