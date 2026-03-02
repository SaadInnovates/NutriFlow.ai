from datetime import datetime, timezone
import json
import logging
from typing import Any


audit_logger = logging.getLogger("security.audit")


def audit_event(
	event: str,
	success: bool,
	email: str | None = None,
	ip: str | None = None,
	detail: str | None = None,
	metadata: dict[str, Any] | None = None,
) -> None:
	payload = {
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"event": event,
		"success": success,
		"email": email,
		"ip": ip,
		"detail": detail,
		"metadata": metadata or {},
	}
	audit_logger.info(json.dumps(payload, sort_keys=True))
