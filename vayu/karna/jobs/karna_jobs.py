# vayu/karna/jobs/karna_jobs.py
"""
Web-accessible job wrappers for Karna CLI flows.
Makes all crew functions callable via Python or HTTP.
"""

from vayu.karna.flows import karna_flow

from vayu.karna.tools.airtable_utils import (
    list_active_clients,
    create_job_record,
    update_job_status
)

def curate_one(client_id: str, num_ideas: int = 20, verbose: bool = True):
    """Curate ideas for one client."""
    return karna_flow.curate_only(client_id, num_ideas=num_ideas, verbose=verbose)

def create_posts_one(client_id: str, num_posts: int = 3, verbose: bool = True):
    """Create posts for one client."""
    return karna_flow.create_posts_only(client_id, num_posts=num_posts, verbose=verbose)

def publish_one(client_id: str, verbose: bool = True):
    """Publish approved posts for one client."""
    return karna_flow.publish_only(client_id, verbose=verbose)

def full_workflow_one(client_id: str, num_ideas: int = 20, num_posts: int = 3, verbose: bool = True):
    """Run full workflow (curate → create posts → publish) for one client."""
    return karna_flow.full_workflow(client_id, num_ideas=num_ideas, num_posts=num_posts, verbose=verbose)

def curate_all(max_clients: int = None, num_ideas: int = 20, verbose: bool = True):
    """Curate for all active clients."""
    return karna_flow.curate_all_clients(max_clients=max_clients, num_ideas=num_ideas, verbose=verbose)

def create_posts_all(max_clients: int = None, num_posts: int = 3, verbose: bool = True):
    """
    Create posts for all active clients.
    Logs parent + child jobs in Airtable (Jobs table).
    """
    from vayu.karna.flows import karna_flow
    from vayu.karna.tools.airtable_utils import (
        list_active_clients,
        create_job_record,
        update_job_status
    )

    # ✅ 1. Create parent job record
    parent_job_id = create_job_record("create_posts_all")

    try:
        update_job_status(parent_job_id, "Running")

        # ✅ 2. Get active clients
        clients = list_active_clients()
        if max_clients:
            clients = clients[:max_clients]

        print(f"[JOBS] Running create_posts_all for {len(clients)} clients")

        results = {}
        for client in clients:
            client_id = client["id"]
            client_name = client["fields"].get("Name", "Unknown")

            print(f"\n{'-'*50}")
            print(f"✍️ Creating posts for {client_name}")
            print(f"{'-'*50}")

            # ✅ Child job record per client
            child_job_id = create_job_record("create_posts", client_id, {"num_posts": num_posts})
            try:
                update_job_status(child_job_id, "Running")
                result = karna_flow.create_posts_only(client_id, num_posts=num_posts, verbose=verbose)
                update_job_status(child_job_id, "Completed", result_summary=result)
                results[client_id] = result
            except Exception as e:
                update_job_status(child_job_id, "Failed", error=str(e))
                print(f"[JOBS] ❌ Failed for {client_name}: {e}")

        # ✅ 3. Mark parent job completed
        update_job_status(parent_job_id, "Completed", result_summary=results)
        print(f"[JOBS] ✅ All clients post creation complete.")
        return {"job_id": parent_job_id, "clients_processed": len(clients)}

    except Exception as e:
        update_job_status(parent_job_id, "Failed", error=str(e))
        print(f"[JOBS] ❌ create_posts_all failed: {e}")
        raise


def full_workflow_all(max_clients: int = None, num_ideas: int = 20, num_posts: int = 3, verbose: bool = True):
    """Run full workflow for all active clients."""
    return karna_flow.full_workflow_all_clients(max_clients=max_clients, num_ideas=num_ideas, num_posts=num_posts, verbose=verbose)

def submit_client_input_job(client_id: str, idea_text: str, image_url: str = None, channel: str = "Facebook", verbose: bool = True):
    """Simulate a WhatsApp/web-form submission."""
    return karna_flow.submit_client_input(client_id, idea_text, image_url=image_url, channel=channel, verbose=verbose)



# =====================================================
# 🔹 LAYER 2: ASYNC BACKGROUND JOBS (with Airtable tracking)
# =====================================================

def create_posts_job(client_id: str, num_ideas: int = 10, num_posts: int = 3):
    """Background job: curate ideas + create posts (no publishing)."""
    #print(f"{client_id}")
    job_id = create_job_record("create_posts", client_id)
    if not client_id or not client_id.startswith("rec"):
        print(f"[JOBS] ⚠️ Invalid client_id passed: {client_id}")
    else:
        job_id = create_job_record("create_posts", client_id)   
    try:
        update_job_status(job_id, "Running")
        karna_flow.curate_only(client_id, num_ideas=num_ideas, verbose=True)
        karna_flow.create_posts_only(client_id, num_posts=num_posts, verbose=True)
        update_job_status(job_id, "Completed")
    except Exception as e:
        update_job_status(job_id, "Failed", error=str(e))
        print(f"[JOBS] ❌ Failed create_posts_job for {client_id}: {e}")

def publish_job(client_id: str):
    """Background job: publish approved posts."""
    if not client_id or not client_id.startswith("rec"):
        print(f"[JOBS] ⚠️ Invalid client_id passed: {client_id}")
    else:
        job_id = create_job_record("publish_posts", client_id)   
    try:
        update_job_status(job_id, "Running")
        karna_flow.publish_only(client_id, verbose=True)
        update_job_status(job_id, "Completed")
    except Exception as e:
        update_job_status(job_id, "Failed", error=str(e))
        print(f"[JOBS] ❌ Failed publish_job for {client_id}: {e}")
        
def publish_all(max_clients: int = None, verbose: bool = True):
    """
    Publish approved posts for all active clients.
    Creates a top-level 'publish_all' Job record,
    and individual child jobs per client for tracking.
    """
    from vayu.karna.flows import karna_flow
    from vayu.karna.tools.airtable_utils import (
        list_active_clients,
        create_job_record,
        update_job_status
    )

    # ✅ 1. Create parent job record in Airtable
    parent_job_id = create_job_record("publish_all_clients")

    try:
        update_job_status(parent_job_id, "Running")

        # ✅ 2. Fetch clients
        clients = list_active_clients()
        if max_clients:
            clients = clients[:max_clients]

        print(f"[JOBS] Running publish_all for {len(clients)} clients")

        results = {}
        for client in clients:
            client_id = client["id"]
            client_name = client["fields"].get("Name", "Unknown")

            print(f"\n{'-'*50}")
            print(f"📤 Publishing for {client_name}")
            print(f"{'-'*50}")

            # 🧩 Create a child job for each client
            child_job_id = create_job_record("publish_posts", client_id)
            try:
                update_job_status(child_job_id, "Running")
                result = karna_flow.publish_only(client_id, verbose=verbose)
                update_job_status(child_job_id, "Completed", result_summary=result)
                results[client_id] = result
            except Exception as e:
                update_job_status(child_job_id, "Failed", error=str(e))
                print(f"[JOBS] ❌ Failed for {client_name}: {e}")

        # ✅ 3. Mark parent as completed
        update_job_status(parent_job_id, "Completed", result_summary=results)
        print(f"[JOBS] ✅ All clients publishing complete.")

        return {"job_id": parent_job_id, "clients_processed": len(clients)}

    except Exception as e:
        update_job_status(parent_job_id, "Failed", error=str(e))
        print(f"[JOBS] ❌ publish_all failed: {e}")
        raise
