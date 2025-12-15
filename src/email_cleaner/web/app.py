"""Flask web application for email cleaner UI."""

import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session
from ..config import load_config, Config, EmailConfig, AgentConfig
from ..agents import JunkDetectorAgent
from ..services import IMAPEmailClient


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

    # Store scan results in memory (for demo purposes)
    app.scan_results = {}

    @app.route("/")
    def index():
        """Main dashboard page."""
        return render_template("index.html")

    @app.route("/api/connect", methods=["POST"])
    def api_connect():
        """Test email connection."""
        data = request.json
        try:
            config = _create_config_from_request(data)
            with IMAPEmailClient(config.email) as client:
                folders = client.list_folders()
            return jsonify({
                "success": True,
                "folders": folders,
                "message": "Connected successfully!"
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

    @app.route("/api/folders", methods=["POST"])
    def api_folders():
        """Get list of email folders."""
        data = request.json
        try:
            config = _create_config_from_request(data)
            with IMAPEmailClient(config.email) as client:
                folders = client.list_folders()
            return jsonify({
                "success": True,
                "folders": folders
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        """Scan emails for junk."""
        data = request.json
        try:
            config = _create_config_from_request(data)
            folder = data.get("folder", "INBOX")
            limit = int(data.get("limit", 50))
            search = data.get("search", "ALL")

            agent = JunkDetectorAgent(config)
            report = agent.scan_emails(
                folder=folder,
                limit=limit,
                search_criteria=search
            )

            # Get detailed results
            junk_details = agent.get_junk_details(report)

            # Store results for later cleanup
            scan_id = os.urandom(8).hex()
            app.scan_results[scan_id] = {
                "config": config,
                "report": report,
            }

            # Build response with all emails
            all_emails = []
            for email, classification in report.classifications:
                all_emails.append({
                    "uid": email.uid,
                    "subject": email.subject,
                    "sender": email.sender,
                    "sender_name": email.sender_name,
                    "date": email.received_date.isoformat(),
                    "folder": email.folder,
                    "is_junk": classification.is_junk,
                    "confidence": classification.confidence,
                    "indicators": [ind.value for ind in classification.indicators],
                    "reasons": classification.reasons,
                    "recommended_action": classification.recommended_action,
                })

            return jsonify({
                "success": True,
                "scan_id": scan_id,
                "total_scanned": report.total_emails_scanned,
                "junk_found": report.junk_emails_found,
                "emails": all_emails,
                "junk_emails": junk_details,
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

    @app.route("/api/clean", methods=["POST"])
    def api_clean():
        """Clean junk emails."""
        data = request.json
        scan_id = data.get("scan_id")
        dry_run = data.get("dry_run", True)
        email_uids = data.get("email_uids", [])  # Optional: specific emails to clean

        if scan_id not in app.scan_results:
            return jsonify({
                "success": False,
                "message": "Scan results not found. Please scan again."
            }), 400

        try:
            stored = app.scan_results[scan_id]
            config = stored["config"]
            report = stored["report"]

            # Filter to only selected emails if specified
            if email_uids:
                report.classifications = [
                    (email, cls) for email, cls in report.classifications
                    if email.uid in email_uids and cls.is_junk
                ]
                report.junk_emails_found = len(report.classifications)

            agent = JunkDetectorAgent(config)
            updated_report = agent.clean_junk(report, dry_run=dry_run)

            return jsonify({
                "success": True,
                "dry_run": dry_run,
                "deleted": updated_report.emails_deleted,
                "moved_to_spam": updated_report.emails_moved_to_spam,
                "for_review": updated_report.emails_for_review,
                "errors": updated_report.errors,
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

    @app.route("/api/delete", methods=["POST"])
    def api_delete():
        """Delete specific emails."""
        data = request.json
        email_uids = data.get("email_uids", [])
        folder = data.get("folder", "INBOX")

        if not email_uids:
            return jsonify({
                "success": False,
                "message": "No emails specified"
            }), 400

        try:
            config = _create_config_from_request(data)
            deleted = 0
            errors = []

            with IMAPEmailClient(config.email) as client:
                for uid in email_uids:
                    try:
                        if client.move_to_trash(uid, folder):
                            deleted += 1
                        else:
                            errors.append(f"Failed to delete email {uid}")
                    except Exception as e:
                        errors.append(f"Error deleting {uid}: {e}")

            return jsonify({
                "success": True,
                "deleted": deleted,
                "errors": errors,
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 400

    return app


def _create_config_from_request(data: dict) -> Config:
    """Create config from request data."""
    email_config = EmailConfig(
        imap_server=data.get("imap_server", "imap.gmail.com"),
        imap_port=int(data.get("imap_port", 993)),
        email_address=data.get("email_address", ""),
        email_password=data.get("email_password", ""),
    )
    agent_config = AgentConfig(
        dry_run=data.get("dry_run", True),
        max_emails_to_process=int(data.get("limit", 100)),
        junk_confidence_threshold=float(data.get("threshold", 0.7)),
    )
    return Config(email=email_config, agent=agent_config)


def run_server():
    """Run the Flask development server."""
    import click

    @click.command()
    @click.option("--host", default="127.0.0.1", help="Host to bind to")
    @click.option("--port", default=5000, help="Port to bind to")
    @click.option("--debug", is_flag=True, help="Enable debug mode")
    def serve(host: str, port: int, debug: bool):
        """Start the Email Cleaner web UI."""
        app = create_app()
        print(f"\n🧹 Email Cleaner UI starting at http://{host}:{port}\n")
        app.run(host=host, port=port, debug=debug)

    serve()
