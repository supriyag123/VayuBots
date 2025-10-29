# -*- coding: utf-8 -*-
"""
agents/karna.py

Master orchestrator for Karna marketing agents.
Coordinates the crew to execute the full content workflow.
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from crewai import Crew, Process
from datetime import datetime

from vayu.karna.agents.idea_agent import create_idea_agent
from vayu.karna.agents.post_agent import create_post_agent
from vayu.karna.agents.publisher_agent import create_publisher_agent
from vayu.karna.tasks import (
    create_idea_curation_task,
    create_post_creation_task,
    create_publishing_task,
)

from vayu.karna.tools.airtable_utils import list_active_clients, get_client_config, _tbl


class KarnaMarketingCrew:
    """
    Master crew for Karna marketing operations.
    Coordinates multiple agents to handle the full content workflow.
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize the Karna marketing crew.

        Args:
            verbose: Whether to print detailed execution logs
        """
        self.verbose = verbose

        # Initialize agents
        self.idea_agent = create_idea_agent()
        self.post_agent = create_post_agent()
        self.publisher_agent = create_publisher_agent()

    def run_idea_curation(self, client_id: str, num_ideas: int = 20):
        """Run idea curation for a single client."""
        print("\n" + "=" * 60)
        print("🧠 Karna Idea Curation")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # ✅ Get client info
        try:
            client_config = get_client_config(client_id)
            client_name = client_config["name"]
            print(f"Client: {client_name}")
            print(f"Client ID: {client_id}")
            print(f"Max Ideas: {num_ideas}\n")
        except Exception as e:
            print(f"❌ ERROR loading client: {e}")
            return None

        # ✅ Fetch ideas from Airtable
        try:
            table = _tbl("Ideas")
            all_ideas = table.all(max_records=200)

            # Filter only this client's ideas
            client_ideas = [
                idea for idea in all_ideas
                if client_id in idea["fields"].get("Client", [])
            ]

            # ✅ Only pick ideas that are NEW
            new_ideas = [
                idea for idea in client_ideas
                if idea["fields"].get("Status") == "New"
            ]

            if not new_ideas:
                print("⚠️ No new ideas found for curation.")
                return None

            curated_candidates = new_ideas[:num_ideas]
            print(f"🧩 Total new ideas selected for curation: {len(curated_candidates)}")
            for idea in curated_candidates:
                headline = idea["fields"].get("Headline", "Untitled")
                print(f"   - {headline[:60]}")

        except Exception as e:
            print(f"❌ Error fetching ideas: {e}")
            return None

        # ✅ Create the curation task
        curation_task = create_idea_curation_task(
            agent=self.idea_agent,
            client_id=client_id,
            client_name=client_name,
            num_ideas=len(curated_candidates)
        )

        # ✅ Build the workflow
        workflow = Crew(
            agents=[self.idea_agent],
            tasks=[curation_task],
            process=Process.sequential,
            verbose=self.verbose
        )

        # ✅ Run the curation process
        try:
            result = workflow.kickoff()
            print("\n" + "=" * 60)
            print("✅ Curation Complete!")
            print("=" * 60 + "\n")
            print(result)

            # ✅ Update curated ideas in Airtable
            try:
                for idea in curated_candidates:
                    table.update(idea["id"], {
                        "Status": "Curated",
                        "Curation Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                print(f"✅ Updated {len(curated_candidates)} ideas to Status = 'Curated'")
            except Exception as e:
                print(f"⚠️ Warning: could not update idea status: {e}")

            return result

        except Exception as e:
            print(f"\n❌ ERROR during curation: {e}")
            import traceback
            traceback.print_exc()
            return None


    def run_post_creation(self, client_id, idea_ids=None, num_ideas=3):
        """
        Run post creation for a client's top ideas.
    
        Args:
            client_id: Airtable client record ID
            idea_ids: Specific idea IDs, or None to get top priority
            num_ideas: Number of ideas to create posts from
        """
        print(f"\n{'='*60}")
        print(f"✍️  Karna Post Creation")
        print(f"{'='*60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
        # Get client info
        try:
            client_config = get_client_config(client_id)
            client_name = client_config['name']
            print(f"Client: {client_name}")
            print(f"Client ID: {client_id}\n")
        except Exception as e:
            print(f"❌ Error loading client: {e}")
            return None
    
        # If no idea_ids provided, get top priority ideas from Airtable
        if not idea_ids:
            table = _tbl("Ideas")
            print("[DEBUG] Fetching all ideas...")
            all_ideas = table.all(max_records=100)
    
            client_ideas = [
                idea for idea in all_ideas 
                if client_id in idea['fields'].get('Client', [])
            ]
            print(f"[DEBUG] Total ideas for client: {len(client_ideas)}")
    
            # Filter for High priority, Curated
            ideas = [
                idea for idea in client_ideas
                if idea['fields'].get('Priority') == 'High'
                and idea['fields'].get('Status') == 'Curated'
                and idea['fields'].get('Status') != 'Processed'
            ]
    
            # Sort by Quality Score
            ideas.sort(key=lambda x: x['fields'].get('Quality Score', 0), reverse=True)
            ideas = ideas[:num_ideas]
    
            # Fallback: try Medium priority if no High found
            if not ideas:
                ideas = [
                    idea for idea in client_ideas
                    if idea['fields'].get('Priority') == 'Medium'
                    and idea['fields'].get('Status') == 'Curated'
                    and idea['fields'].get('Status') != 'Processed'
                ]
                ideas.sort(key=lambda x: x['fields'].get('Quality Score', 0), reverse=True)
                ideas = ideas[:num_ideas]
    
            idea_ids = [idea['id'] for idea in ideas]
    
            if idea_ids:
                print(f"✓ Selected {len(idea_ids)} ideas:")
                for idea in ideas:
                    headline = idea['fields'].get('Headline', 'No headline')
                    score = idea['fields'].get('Quality Score', 0)
                    print(f"   - {headline[:60]}... (Score {score})")
            else:
                print("❌ No unprocessed high/medium priority ideas found")
                return None
    
        # Create task
        post_task = create_post_creation_task(
            agent=self.post_agent,
            client_id=client_id,
            idea_ids=idea_ids
        )
    
        # Create crew
        crew = Crew(
            agents=[self.post_agent],
            tasks=[post_task],
            process=Process.sequential,
            verbose=self.verbose
        )
    
        # Execute
        try:
            result = crew.kickoff()
            print(f"\n{'='*60}")
            print(f"✅ Post Creation Complete!")
            print(f"{'='*60}\n")
            print(result)
            return result
        
            
            # ✅ Guarantee Airtable persistence (safe even if agent already saved)
            try:
                posts_data = result.get("posts", [])
                if not posts_data:
                    print("⚠️ No posts returned by crew, skipping save.")
                else:
                    table_posts = _tbl("Posts")
                    table_ideas = _tbl("Ideas")
        
                    print(f"💾 Ensuring {len(posts_data)} posts are in Airtable...")
                    for post in posts_data:
                        idea_id = post.get("idea_id")
                        client_id = post.get("client_id")
                        
                        # 👇 Fetch client approval mode dynamically
                        client_config = get_client_config(client_id)
                        approval_mode = client_config.get("approval_mode", "Manager")
                        approval_status = "Auto-Approved" if approval_mode == "Auto" else "Needs Approval"
        
                        # skip if already saved
                        existing = table_posts.all(formula=f"{{Idea}} = '{idea_id}'")
                        if existing:
                            print(f"⚠️ Post already exists for idea {idea_id}, skipping.")
                            continue
        
                        fields = {
                            "Client": [client_id],
                            "Idea": [idea_id],
                            "Caption": post.get("caption"),
                            "Hashtags": post.get("hashtags"),
                            "CTA": post.get("cta"),
                            "Quality Score": post.get("quality_score"),
                            "Publish Status": "Draft",
                            "Approval Status": approval_status
                        }
                        table_posts.create(fields)
                        table_ideas.update(idea_id, {"Status": "Processed"})
                    print("✅ Airtable sync complete.")
            except Exception as e:
                print(f"❌ Error saving posts to Airtable: {e}")
        
            return result
                
        
    
        except Exception as e:
            print(f"\n❌ Error during post creation: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def run_publishing(self, client_id=None):
        """Publish approved posts to social media platforms."""
        print(f"\n{'='*60}")
        print(f"📤 Karna Publishing Workflow")
        print(f"{'='*60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
        # Create task
        publishing_task = create_publishing_task(
            agent=self.publisher_agent,
            client_id=client_id
        )
    
        # Create execution workflow
        workflow = Crew(
            agents=[self.publisher_agent],
            tasks=[publishing_task],
            process=Process.sequential,
            verbose=self.verbose
        )
    
        try:
            result = workflow.kickoff()
            print("\n[DEBUG] Raw publishing result:")
            print(result)
    
            # Parse into structured report
            report = {
                "total_processed": 0,
                "success": [],
                "failed": []
            }
    
            import json
            result_data = {}  # ✅ Always initialize
            if isinstance(result, str):
                try:
                    result_data = json.loads(result)
                    if "posts" in result_data:
                        report["total_processed"] = len(result_data["posts"])
                        for post in result_data["posts"]:
                            if post.get("platform_post_id"):
                                report["success"].append(post)
                            else:
                                report["failed"].append(post)
                except json.JSONDecodeError:
                    print("⚠️ Could not parse result JSON, using raw output")
    
            print("\n===== Publishing Report =====")
            if "posts" in result_data:
                for post in result_data["posts"]:
                    if post.get("success"):
                        print(
                            f"✅ Post {post['record_id']} → {post['channel']} "
                            f"→ Platform Post ID: {post.get('platform_post_id', 'N/A')}"
                        )
                    else:
                        print(
                            f"❌ Post {post.get('record_id', '?')} → "
                            f"Error: {post.get('error', 'Unknown')}"
                        )
            else:
                print("⚠️ No posts found in result_data")

    
            return report
    
        except Exception as e:
            print(f"\n❌ ERROR in publishing: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_full_workflow(self, client_id, num_ideas=20, num_posts=3):
        print("\n" + "=" * 60)
        print("🚀 Karna Full Marketing Workflow")
        print("=" * 60 + "\n")
    
        # Step 1: Curate ideas
        print("📋 Step 1: Curating ideas...")
        curation_result = self.run_idea_curation(client_id, num_ideas=num_ideas)
        if not curation_result:
            print("❌ Curation failed, stopping workflow")
            return None
    
        # Step 2: Create posts
        print("✍️ Step 2: Creating posts...")
        post_result = self.run_post_creation(client_id, num_ideas=num_posts)
    
        # Step 3: Publish
        print("📤 Step 3: Publishing posts...")
        publish_result = self.run_publishing(client_id)
    
        print("\n" + "=" * 60)
        print("✅ Workflow Complete!")
        print("=" * 60 + "\n")
    
        return {
            "curation": curation_result,
            "posts": post_result,
            "publishing": publish_result
        }

    
    def run_curation_for_all_clients(self, max_clients: int = None):
        """Run only idea curation for all active clients."""
        print("\n" + "=" * 60)
        print("🌍 Karna Multi-Client Curation")
        print("=" * 60 + "\n")
    
        clients = list_active_clients()
        if max_clients:
            clients = clients[:max_clients]
    
        if not clients:
            print("❌ No active clients found!")
            return {}
    
        results = {}
        for client in clients:
            client_id = client["id"]
            client_name = client["fields"].get("Name", "Unknown")
    
            print("\n" + "-" * 60)
            print(f"📋 Curating ideas for {client_name}")
            print("-" * 60 + "\n")
    
            curation = self.run_idea_curation(client_id, num_ideas=10)
            results[client_id] = {"name": client_name, "curation": curation}
    
        print("\n" + "=" * 60)
        print("✅ Multi-Client Curation Complete!")
        print("=" * 60 + "\n")
    
        return results
    
    
    def run_post_creation_for_all_clients(self, num_posts: int = 3, max_clients: int = None):
        """Run post creation for all active clients."""
        print("\n" + "=" * 60)
        print("🌍 Karna Multi-Client Post Creation")
        print("=" * 60 + "\n")
    
        clients = list_active_clients()
        if max_clients:
            clients = clients[:max_clients]
    
        if not clients:
            print("❌ No active clients found!")
            return {}
    
        results = {}
        for client in clients:
            client_id = client["id"]
            client_name = client["fields"].get("Name", "Unknown")
    
            print("\n" + "-" * 60)
            print(f"✍️ Creating posts for {client_name}")
            print("-" * 60 + "\n")
    
            posts = self.run_post_creation(client_id, num_ideas=num_posts)
            results[client_id] = {"name": client_name, "posts": posts}
    
        print("\n" + "=" * 60)
        print("✅ Multi-Client Post Creation Complete!")
        print("=" * 60 + "\n")
    
        return results
    
    
    def run_full_workflow_for_all_clients(self, max_clients: int = None, num_ideas: int = 20, num_posts: int = 3):
        """Run full workflow (curate → create posts → publish) for all active clients."""
        print("\n" + "=" * 60)
        print("🌍 Karna Multi-Client Full Workflow")
        print("=" * 60 + "\n")
    
        clients = list_active_clients()
        if max_clients:
            clients = clients[:max_clients]
    
        if not clients:
            print("❌ No active clients found!")
            return {}
    
        results = {}
        for client in clients:
            client_id = client["id"]
            client_name = client["fields"].get("Name", "Unknown")
    
            print("\n" + "-" * 60)
            print(f"🚀 Running full workflow for {client_name}")
            print("-" * 60 + "\n")
    
            workflow = self.run_full_workflow(
                client_id,
                num_ideas=num_ideas,
                num_posts=num_posts
            )
            results[client_id] = {"name": client_name, "workflow": workflow}
    
        print("\n" + "=" * 60)
        print("✅ Multi-Client Full Workflow Complete!")
        print("=" * 60 + "\n")
    
        return results

# ============================================================================ #
# Convenience Functions
# ============================================================================ #

def run_curation_for_client(client_id: str, num_ideas: int = 20, verbose: bool = True):
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_idea_curation(client_id, num_ideas)


def run_curation_for_all_active_clients(max_clients: int = None, verbose: bool = True):
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_curation_for_all_clients(max_clients)


def run_post_creation_for_all_active_clients(num_posts: int = 3, verbose: bool = True):
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_post_creation_for_all_clients(num_posts)


def run_full_workflow_for_all_active_clients(max_clients: int = None, verbose: bool = True):
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_full_workflow_for_all_clients(max_clients)


# ============================================================================ #
# Main
# ============================================================================ #
# -*- coding: utf-8 -*-
"""
CLI entrypoint for Karna.
Delegates to flows/karna_flow.py wrapper functions.
"""

import argparse
from vayu.karna.flows import karna_flow  # ✅ use the new wrapper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Karna Marketing Crew")
    parser.add_argument('--client-id', type=str, help='Specific client ID to process')
    parser.add_argument('--all-clients', action='store_true', help='Process all active clients')
    parser.add_argument('--max-clients', type=int, help='Max clients to process (for testing)')
    parser.add_argument('--num-ideas', type=int, default=20, help='Max ideas per client')
    parser.add_argument('--create-posts', action='store_true', help='Create posts from curated ideas')
    parser.add_argument('--num-posts', type=int, default=3, help='Number of posts to create per client')
    parser.add_argument('--publish', action='store_true', help='Publish approved posts')
    parser.add_argument('--full-workflow', action='store_true', help='Run full workflow (curation → posts → publish)')
    parser.add_argument('--client-input', type=str, help='Raw client idea text (simulates WhatsApp/web input)')
    parser.add_argument('--image-url', type=str, help='Optional image URL to attach to client idea')
    parser.add_argument('--channel', type=str, default="Facebook", help='Channel for posts (Facebook/Instagram/LinkedIn)')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')

    args = parser.parse_args()
    verbose = not args.quiet

    # -------------------------------------------------------------
    # SPECIAL MODE: client direct input (WhatsApp/Web)
    # -------------------------------------------------------------
    if args.client_id and args.client_input:
        result = karna_flow.submit_client_input(
            client_id=args.client_id,
            idea_text=args.client_input,
            image_url=args.image_url,
            channel=args.channel,
            verbose=verbose
        )
        print(result)

    # -------------------------------------------------------------
    # SINGLE CLIENT MODES
    # -------------------------------------------------------------
    elif args.client_id:
        if args.full_workflow:
            karna_flow.full_workflow(
                args.client_id,
                num_ideas=args.num_ideas,
                num_posts=args.num_posts,
                verbose=verbose
            )

        elif args.create_posts:
            karna_flow.create_posts_only(
                args.client_id,
                num_posts=args.num_posts,
                verbose=verbose
            )

        elif args.publish:
            karna_flow.publish_only(
                args.client_id,
                verbose=verbose
            )

        else:
            karna_flow.curate_only(
                args.client_id,
                num_ideas=args.num_ideas,
                verbose=verbose
            )

    # -------------------------------------------------------------
    # MULTI-CLIENT MODES
    # -------------------------------------------------------------
    elif args.all_clients:
        if args.full_workflow:
            karna_flow.full_workflow_all_clients(
                max_clients=args.max_clients,
                num_ideas=args.num_ideas,
                num_posts=args.num_posts,
                verbose=verbose
            )

        elif args.create_posts:
            karna_flow.create_posts_all_clients(
                num_posts=args.num_posts,
                max_clients=args.max_clients,
                verbose=verbose
            )

        else:
            karna_flow.curate_all_clients(
                max_clients=args.max_clients,
                verbose=verbose
            )

    # -------------------------------------------------------------
    # DEFAULT BEHAVIOUR (no client_id, no all_clients)
    # -------------------------------------------------------------
    else:
        print("Usage examples:")
        print("  Single client curation:   python karna.py --client-id recXXXXXX")
        print("  All clients curation:     python karna.py --all-clients")
        print("  Create posts (1 client):  python karna.py --client-id recXXXXXX --create-posts --num-posts 3")
        print("  Create posts (all):       python karna.py --all-clients --create-posts --num-posts 3")
        print("  Publish (1 client):       python karna.py --client-id recXXXXXX --publish")
        print("  Full workflow (1 client): python karna.py --client-id recXXXXXX --full-workflow")
        print("  Full workflow (all):      python karna.py --all-clients --full-workflow")
        print("  Submit client input:      python karna.py --client-id recXXXXXX --client-input 'My idea text' --image-url https://... --channel Facebook")
