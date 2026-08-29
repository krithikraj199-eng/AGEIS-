"""
AEGIS Ω — Digital Institution Builder

Creates the complete virtual university with departments, assets,
dependency relationships, and realistic initial metrics.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from .models import (
    Asset, AssetMetrics, AssetStatus, AssetType,
    Department
)


class InstitutionBuilder:
    """Constructs the complete digital institution."""

    def __init__(self):
        self.assets: Dict[str, Asset] = {}
        self._build_institution()

    # ──────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────

    def get_all_assets(self) -> Dict[str, Asset]:
        return self.assets

    def get_asset(self, asset_id: str) -> Asset | None:
        return self.assets.get(asset_id)

    def get_assets_by_type(self, asset_type: AssetType) -> List[Asset]:
        return [a for a in self.assets.values() if a.asset_type == asset_type]

    def get_assets_by_department(self, dept: Department) -> List[Asset]:
        return [a for a in self.assets.values() if a.department == dept]

    def get_asset_count(self) -> int:
        return len(self.assets)

    # ──────────────────────────────────────────────────────
    # PRIVATE — build everything
    # ──────────────────────────────────────────────────────

    def _build_institution(self):
        """Build the entire digital university."""
        # Layer 0: Core infrastructure
        self._build_core_infrastructure()
        # Layer 1: Databases
        self._build_databases()
        # Layer 2: Services / APIs
        self._build_services()
        # Layer 3: Applications
        self._build_applications()
        # Layer 4: Network nodes
        self._build_network()
        # Layer 5: Workstations
        self._build_workstations()
        # Wire dependencies
        self._wire_dependencies()

    def _add(self, asset: Asset):
        self.assets[asset.asset_id] = asset

    # ── CORE INFRASTRUCTURE ──────────────────────────────

    def _build_core_infrastructure(self):
        """Firewalls, load balancers, storage."""
        infra = [
            ("FW-MAIN-01", "Main Firewall", AssetType.FIREWALL, 10),
            ("FW-DMZ-01", "DMZ Firewall", AssetType.FIREWALL, 9),
            ("LB-WEB-01", "Web Load Balancer", AssetType.LOAD_BALANCER, 9),
            ("LB-API-01", "API Load Balancer", AssetType.LOAD_BALANCER, 9),
            ("SAN-01", "Primary SAN Storage", AssetType.STORAGE, 10),
            ("SAN-02", "Backup SAN Storage", AssetType.STORAGE, 8),
            ("DNS-01", "Primary DNS Server", AssetType.SERVER, 10),
            ("DNS-02", "Secondary DNS Server", AssetType.SERVER, 8),
            ("NTP-01", "NTP Time Server", AssetType.SERVER, 7),
            ("SMTP-01", "Mail Server", AssetType.SERVER, 6),
            ("LDAP-01", "Active Directory / LDAP", AssetType.SERVER, 10),
            ("PROXY-01", "Reverse Proxy", AssetType.SERVER, 8),
            ("MONITOR-01", "Monitoring Server", AssetType.SERVER, 7),
            ("BACKUP-01", "Backup Server", AssetType.SERVER, 7),
            ("LOG-01", "Central Log Server", AssetType.SERVER, 7),
        ]
        for aid, name, atype, crit in infra:
            self._add(Asset(
                asset_id=aid, name=name, asset_type=atype,
                department=Department.INFRASTRUCTURE,
                criticality=crit,
                metrics=self._healthy_metrics(atype),
                tags=["core", "infrastructure"],
            ))

    # ── DATABASES ────────────────────────────────────────

    def _build_databases(self):
        dbs = [
            ("DB-MAIN-01", "Main PostgreSQL Cluster", 10),
            ("DB-MAIN-02", "PostgreSQL Read Replica", 8),
            ("DB-STUDENT-01", "Student Records DB", 9),
            ("DB-STAFF-01", "Staff & HR Database", 8),
            ("DB-LIBRARY-01", "Library Catalog DB", 6),
            ("DB-EXAM-01", "Examination Database", 9),
            ("DB-FINANCE-01", "Finance Database", 9),
            ("DB-ATTENDANCE-01", "Attendance Database", 7),
            ("DB-ANALYTICS-01", "Analytics Data Warehouse", 5),
            ("DB-CONFIG-01", "Configuration Store", 8),
        ]
        for aid, name, crit in dbs:
            self._add(Asset(
                asset_id=aid, name=name, asset_type=AssetType.DATABASE,
                department=Department.INFRASTRUCTURE,
                criticality=crit,
                metrics=self._healthy_metrics(AssetType.DATABASE),
                tags=["database", "data-tier"],
            ))

    # ── SERVICES / APIs ──────────────────────────────────

    def _build_services(self):
        services = [
            ("SVC-AUTH-01", "Authentication Service", Department.INFRASTRUCTURE, 10),
            ("SVC-AUTH-02", "OAuth / SSO Gateway", Department.INFRASTRUCTURE, 9),
            ("API-STUDENT-01", "Student API", Department.COMPUTER_SCIENCE, 9),
            ("API-STAFF-01", "Staff API", Department.ADMINISTRATION, 8),
            ("API-EXAM-01", "Examination API", Department.ADMINISTRATION, 9),
            ("API-LIBRARY-01", "Library API", Department.LIBRARY, 6),
            ("API-ATTENDANCE-01", "Attendance API", Department.ADMINISTRATION, 8),
            ("API-FINANCE-01", "Finance API", Department.ADMINISTRATION, 9),
            ("API-NOTIFICATION-01", "Notification Service", Department.INFRASTRUCTURE, 7),
            ("API-ANALYTICS-01", "Analytics API", Department.INFRASTRUCTURE, 5),
            ("SVC-CACHE-01", "Redis Cache Cluster", Department.INFRASTRUCTURE, 8),
            ("SVC-QUEUE-01", "Message Queue Service", Department.INFRASTRUCTURE, 8),
            ("SVC-SEARCH-01", "Search Service", Department.INFRASTRUCTURE, 6),
            ("SVC-FILE-01", "File Storage Service", Department.INFRASTRUCTURE, 7),
            ("SVC-REPORT-01", "Report Generator Service", Department.ADMINISTRATION, 5),
        ]
        for aid, name, dept, crit in services:
            self._add(Asset(
                asset_id=aid, name=name, asset_type=AssetType.SERVICE,
                department=dept, criticality=crit,
                metrics=self._healthy_metrics(AssetType.SERVICE),
                tags=["service", "api-tier"],
            ))

    # ── APPLICATIONS ─────────────────────────────────────

    def _build_applications(self):
        apps = [
            ("APP-PORTAL-01", "Student Portal", Department.COMPUTER_SCIENCE, 9),
            ("APP-PORTAL-02", "Faculty Portal", Department.ADMINISTRATION, 8),
            ("APP-PORTAL-03", "Admin Dashboard", Department.ADMINISTRATION, 8),
            ("APP-LMS-01", "Learning Management System", Department.COMPUTER_SCIENCE, 8),
            ("APP-EXAM-01", "Online Examination Platform", Department.ADMINISTRATION, 9),
            ("APP-LIBRARY-01", "Digital Library System", Department.LIBRARY, 6),
            ("APP-ATTENDANCE-01", "Attendance Management", Department.ADMINISTRATION, 7),
            ("APP-FINANCE-01", "Fee Payment Portal", Department.ADMINISTRATION, 9),
            ("APP-HR-01", "HR Management System", Department.ADMINISTRATION, 7),
            ("APP-PLACEMENT-01", "Placement Portal", Department.COMPUTER_SCIENCE, 6),
            ("APP-HOSTEL-01", "Hostel Management", Department.ADMINISTRATION, 5),
            ("APP-TRANSPORT-01", "Transport Tracker", Department.ADMINISTRATION, 4),
            ("APP-EMAIL-01", "Institutional Email", Department.INFRASTRUCTURE, 7),
            ("APP-COLLAB-01", "Collaboration Platform", Department.COMPUTER_SCIENCE, 6),
            ("APP-ERP-01", "ERP System", Department.ADMINISTRATION, 9),
            ("APP-FEEDBACK-01", "Feedback System", Department.ADMINISTRATION, 4),
            ("APP-RESEARCH-01", "Research Portal", Department.COMPUTER_SCIENCE, 5),
            ("APP-ALUMNI-01", "Alumni Network", Department.ADMINISTRATION, 3),
            ("APP-HELPDESK-01", "IT Helpdesk", Department.INFRASTRUCTURE, 6),
            ("APP-TIMETABLE-01", "Timetable Manager", Department.ADMINISTRATION, 6),
        ]
        for aid, name, dept, crit in apps:
            self._add(Asset(
                asset_id=aid, name=name, asset_type=AssetType.APPLICATION,
                department=dept, criticality=crit,
                metrics=self._healthy_metrics(AssetType.APPLICATION),
                tags=["application", "user-facing"],
            ))

    # ── NETWORK ──────────────────────────────────────────

    def _build_network(self):
        nodes = [
            ("NET-CORE-01", "Core Switch A", 10),
            ("NET-CORE-02", "Core Switch B", 10),
            ("NET-DIST-CSE", "Distribution Switch — CSE", 8),
            ("NET-DIST-ECE", "Distribution Switch — ECE", 8),
            ("NET-DIST-MECH", "Distribution Switch — Mech", 7),
            ("NET-DIST-CIVIL", "Distribution Switch — Civil", 7),
            ("NET-DIST-ADMIN", "Distribution Switch — Admin", 8),
            ("NET-DIST-LIB", "Distribution Switch — Library", 6),
            ("NET-WIFI-01", "WiFi Controller 1", 8),
            ("NET-WIFI-02", "WiFi Controller 2", 7),
            ("NET-WAN-01", "WAN Gateway", 10),
            ("NET-VPN-01", "VPN Gateway", 8),
        ]
        for aid, name, crit in nodes:
            dept = Department.INFRASTRUCTURE
            self._add(Asset(
                asset_id=aid, name=name, asset_type=AssetType.NETWORK_NODE,
                department=dept, criticality=crit,
                metrics=self._healthy_metrics(AssetType.NETWORK_NODE),
                tags=["network"],
            ))

    # ── WORKSTATIONS ─────────────────────────────────────

    def _build_workstations(self):
        labs = {
            Department.COMPUTER_SCIENCE: [
                ("LAB-CSE-1", 60), ("LAB-CSE-2", 60), ("LAB-CSE-3", 60),
                ("LAB-CSE-4", 40), ("LAB-CSE-RESEARCH", 20),
            ],
            Department.ELECTRONICS: [
                ("LAB-ECE-1", 40), ("LAB-ECE-2", 40), ("LAB-ECE-VLSI", 20),
            ],
            Department.MECHANICAL: [
                ("LAB-MECH-CAD", 30), ("LAB-MECH-SIM", 20),
            ],
            Department.CIVIL: [
                ("LAB-CIVIL-CAD", 20),
            ],
            Department.ADMINISTRATION: [
                ("OFFICE-ADMIN", 30), ("OFFICE-EXAM", 15),
            ],
            Department.LIBRARY: [
                ("LIB-TERMINALS", 40),
            ],
        }

        servers = {
            Department.COMPUTER_SCIENCE: [
                ("SRV-CSE-WEB-01", "CSE Web Server", 7),
                ("SRV-CSE-WEB-02", "CSE Web Server 2", 6),
                ("SRV-CSE-GPU-01", "CSE GPU Compute", 7),
                ("SRV-CSE-DEV-01", "CSE Dev Server", 5),
            ],
            Department.ELECTRONICS: [
                ("SRV-ECE-SIM-01", "ECE Simulation Server", 6),
                ("SRV-ECE-FPGA-01", "ECE FPGA Server", 5),
            ],
            Department.MECHANICAL: [
                ("SRV-MECH-CAD-01", "Mech CAD Server", 6),
            ],
            Department.ADMINISTRATION: [
                ("SRV-ADMIN-01", "Admin File Server", 6),
                ("SRV-ADMIN-02", "Print Server", 4),
            ],
        }

        # Create bulk workstations (keep a representative subset for simulation efficiency)
        ws_count = 0
        for dept, lab_list in labs.items():
            for lab_name, count in lab_list:
                # Create representative workstations (1 per 10 to keep simulation manageable)
                representative = max(1, count // 10)
                for i in range(representative):
                    aid = f"WS-{lab_name}-{i+1:03d}"
                    self._add(Asset(
                        asset_id=aid,
                        name=f"{lab_name} Workstation {i+1}",
                        asset_type=AssetType.WORKSTATION,
                        department=dept,
                        criticality=3,
                        metrics=self._healthy_metrics(AssetType.WORKSTATION),
                        tags=["workstation", lab_name.lower()],
                        metadata={"lab": lab_name, "seat": i+1, "total_seats": count},
                    ))
                    ws_count += 1

        # Create servers per department
        for dept, srv_list in servers.items():
            for aid, name, crit in srv_list:
                self._add(Asset(
                    asset_id=aid, name=name, asset_type=AssetType.SERVER,
                    department=dept, criticality=crit,
                    metrics=self._healthy_metrics(AssetType.SERVER),
                    tags=["server", "department"],
                ))

    # ── DEPENDENCY WIRING ────────────────────────────────

    def _wire_dependencies(self):
        """
        Create realistic dependency relationships.
        This creates the dependency graph that enables
        cascading failure reasoning.
        """
        dep_map: Dict[str, List[str]] = {
            # --- Applications depend on their APIs ---
            "APP-PORTAL-01": ["API-STUDENT-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-PORTAL-02": ["API-STAFF-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-PORTAL-03": ["API-STAFF-01", "API-STUDENT-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-LMS-01": ["API-STUDENT-01", "SVC-AUTH-01", "SVC-FILE-01", "LB-WEB-01"],
            "APP-EXAM-01": ["API-EXAM-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-LIBRARY-01": ["API-LIBRARY-01", "SVC-AUTH-01", "SVC-SEARCH-01"],
            "APP-ATTENDANCE-01": ["API-ATTENDANCE-01", "SVC-AUTH-01"],
            "APP-FINANCE-01": ["API-FINANCE-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-HR-01": ["API-STAFF-01", "SVC-AUTH-01"],
            "APP-ERP-01": ["API-STUDENT-01", "API-STAFF-01", "API-FINANCE-01", "SVC-AUTH-01", "LB-WEB-01"],
            "APP-HELPDESK-01": ["SVC-AUTH-01", "API-NOTIFICATION-01"],
            "APP-EMAIL-01": ["SMTP-01", "LDAP-01"],
            "APP-COLLAB-01": ["SVC-AUTH-01", "SVC-FILE-01", "SVC-QUEUE-01"],
            "APP-RESEARCH-01": ["SVC-AUTH-01", "SVC-FILE-01", "API-STUDENT-01"],
            "APP-TIMETABLE-01": ["API-STUDENT-01", "API-STAFF-01", "SVC-AUTH-01"],
            "APP-PLACEMENT-01": ["API-STUDENT-01", "SVC-AUTH-01"],
            "APP-FEEDBACK-01": ["API-STUDENT-01", "SVC-AUTH-01"],
            "APP-ALUMNI-01": ["SVC-AUTH-01"],
            "APP-HOSTEL-01": ["API-STUDENT-01", "SVC-AUTH-01"],
            "APP-TRANSPORT-01": ["SVC-AUTH-01"],

            # --- APIs depend on databases & services ---
            "API-STUDENT-01": ["DB-STUDENT-01", "SVC-CACHE-01", "LB-API-01"],
            "API-STAFF-01": ["DB-STAFF-01", "SVC-CACHE-01", "LB-API-01"],
            "API-EXAM-01": ["DB-EXAM-01", "SVC-CACHE-01", "LB-API-01"],
            "API-LIBRARY-01": ["DB-LIBRARY-01", "SVC-CACHE-01", "LB-API-01"],
            "API-ATTENDANCE-01": ["DB-ATTENDANCE-01", "SVC-CACHE-01", "LB-API-01"],
            "API-FINANCE-01": ["DB-FINANCE-01", "SVC-CACHE-01", "LB-API-01"],
            "API-ANALYTICS-01": ["DB-ANALYTICS-01", "SVC-CACHE-01", "LB-API-01"],
            "API-NOTIFICATION-01": ["SVC-QUEUE-01", "SMTP-01", "LB-API-01"],

            # --- Services depend on core infra ---
            "SVC-AUTH-01": ["DB-MAIN-01", "LDAP-01", "SVC-CACHE-01"],
            "SVC-AUTH-02": ["SVC-AUTH-01", "DB-MAIN-01"],
            "SVC-CACHE-01": ["NET-CORE-01"],
            "SVC-QUEUE-01": ["NET-CORE-01", "SAN-01"],
            "SVC-SEARCH-01": ["DB-MAIN-01", "SVC-CACHE-01"],
            "SVC-FILE-01": ["SAN-01", "NET-CORE-01"],
            "SVC-REPORT-01": ["DB-ANALYTICS-01", "SVC-QUEUE-01"],

            # --- Databases depend on storage & network ---
            "DB-MAIN-01": ["SAN-01", "NET-CORE-01"],
            "DB-MAIN-02": ["DB-MAIN-01", "SAN-01"],
            "DB-STUDENT-01": ["DB-MAIN-01"],
            "DB-STAFF-01": ["DB-MAIN-01"],
            "DB-LIBRARY-01": ["DB-MAIN-01"],
            "DB-EXAM-01": ["DB-MAIN-01"],
            "DB-FINANCE-01": ["DB-MAIN-01"],
            "DB-ATTENDANCE-01": ["DB-MAIN-01"],
            "DB-ANALYTICS-01": ["DB-MAIN-01", "SAN-02"],
            "DB-CONFIG-01": ["SAN-01"],

            # --- Load balancers depend on network ---
            "LB-WEB-01": ["NET-CORE-01", "FW-DMZ-01"],
            "LB-API-01": ["NET-CORE-01", "FW-MAIN-01"],

            # --- Network distribution depends on core ---
            "NET-DIST-CSE": ["NET-CORE-01", "NET-CORE-02"],
            "NET-DIST-ECE": ["NET-CORE-01", "NET-CORE-02"],
            "NET-DIST-MECH": ["NET-CORE-01"],
            "NET-DIST-CIVIL": ["NET-CORE-01"],
            "NET-DIST-ADMIN": ["NET-CORE-01", "NET-CORE-02"],
            "NET-DIST-LIB": ["NET-CORE-01"],
            "NET-WIFI-01": ["NET-CORE-01"],
            "NET-WIFI-02": ["NET-CORE-02"],
            "NET-WAN-01": ["NET-CORE-01", "FW-MAIN-01"],
            "NET-VPN-01": ["NET-WAN-01", "FW-MAIN-01"],

            # --- Other infra ---
            "DNS-01": ["NET-CORE-01"],
            "DNS-02": ["NET-CORE-02"],
            "SMTP-01": ["NET-CORE-01", "DNS-01"],
            "LDAP-01": ["DB-MAIN-01", "NET-CORE-01"],
            "PROXY-01": ["LB-WEB-01", "DNS-01"],
            "LOG-01": ["SAN-02", "NET-CORE-01"],
            "MONITOR-01": ["NET-CORE-01", "DB-CONFIG-01"],
            "BACKUP-01": ["SAN-02", "NET-CORE-01"],
        }

        for asset_id, deps in dep_map.items():
            if asset_id in self.assets:
                valid_deps = [d for d in deps if d in self.assets]
                self.assets[asset_id].dependencies = valid_deps
                # Also set reverse — dependents
                for dep_id in valid_deps:
                    if dep_id in self.assets:
                        if asset_id not in self.assets[dep_id].dependents:
                            self.assets[dep_id].dependents.append(asset_id)

        # Wire workstations to their department's distribution switch & DNS
        switch_map = {
            Department.COMPUTER_SCIENCE: "NET-DIST-CSE",
            Department.ELECTRONICS: "NET-DIST-ECE",
            Department.MECHANICAL: "NET-DIST-MECH",
            Department.CIVIL: "NET-DIST-CIVIL",
            Department.ADMINISTRATION: "NET-DIST-ADMIN",
            Department.LIBRARY: "NET-DIST-LIB",
        }
        for asset in self.assets.values():
            if asset.asset_type == AssetType.WORKSTATION:
                sw = switch_map.get(asset.department)
                if sw and sw in self.assets:
                    asset.dependencies = [sw, "DNS-01"]
                    if asset.asset_id not in self.assets[sw].dependents:
                        self.assets[sw].dependents.append(asset.asset_id)

    # ── METRIC GENERATORS ────────────────────────────────

    @staticmethod
    def _healthy_metrics(asset_type: AssetType) -> AssetMetrics:
        """Generate realistic healthy baseline metrics."""
        base = {
            AssetType.WORKSTATION: AssetMetrics(
                cpu_percent=random.uniform(10, 45),
                memory_percent=random.uniform(25, 55),
                disk_percent=random.uniform(30, 60),
                network_latency_ms=random.uniform(1, 15),
                error_rate=random.uniform(0, 0.5),
            ),
            AssetType.SERVER: AssetMetrics(
                cpu_percent=random.uniform(15, 50),
                memory_percent=random.uniform(30, 65),
                disk_percent=random.uniform(20, 55),
                network_latency_ms=random.uniform(1, 10),
                error_rate=random.uniform(0, 1.0),
                request_rate=random.uniform(50, 500),
                connection_count=random.randint(10, 200),
                response_time_ms=random.uniform(5, 80),
            ),
            AssetType.DATABASE: AssetMetrics(
                cpu_percent=random.uniform(20, 55),
                memory_percent=random.uniform(40, 70),
                disk_percent=random.uniform(25, 60),
                network_latency_ms=random.uniform(1, 8),
                error_rate=random.uniform(0, 0.2),
                connection_count=random.randint(20, 300),
                response_time_ms=random.uniform(2, 50),
                queue_depth=random.randint(0, 10),
                throughput=random.uniform(100, 1000),
            ),
            AssetType.APPLICATION: AssetMetrics(
                cpu_percent=random.uniform(10, 40),
                memory_percent=random.uniform(20, 50),
                disk_percent=random.uniform(15, 40),
                network_latency_ms=random.uniform(5, 30),
                error_rate=random.uniform(0, 1.5),
                request_rate=random.uniform(20, 300),
                response_time_ms=random.uniform(50, 300),
            ),
            AssetType.SERVICE: AssetMetrics(
                cpu_percent=random.uniform(15, 45),
                memory_percent=random.uniform(25, 55),
                disk_percent=random.uniform(10, 35),
                network_latency_ms=random.uniform(1, 15),
                error_rate=random.uniform(0, 0.8),
                request_rate=random.uniform(100, 800),
                connection_count=random.randint(20, 500),
                response_time_ms=random.uniform(5, 100),
                throughput=random.uniform(200, 2000),
            ),
            AssetType.NETWORK_NODE: AssetMetrics(
                cpu_percent=random.uniform(5, 25),
                memory_percent=random.uniform(15, 40),
                network_latency_ms=random.uniform(0.5, 5),
                throughput=random.uniform(500, 5000),
            ),
            AssetType.FIREWALL: AssetMetrics(
                cpu_percent=random.uniform(10, 35),
                memory_percent=random.uniform(20, 45),
                network_latency_ms=random.uniform(0.5, 3),
                connection_count=random.randint(100, 2000),
                throughput=random.uniform(1000, 10000),
            ),
            AssetType.LOAD_BALANCER: AssetMetrics(
                cpu_percent=random.uniform(10, 30),
                memory_percent=random.uniform(15, 40),
                network_latency_ms=random.uniform(0.5, 5),
                request_rate=random.uniform(200, 2000),
                connection_count=random.randint(50, 1000),
                response_time_ms=random.uniform(1, 10),
            ),
            AssetType.STORAGE: AssetMetrics(
                cpu_percent=random.uniform(5, 20),
                memory_percent=random.uniform(10, 30),
                disk_percent=random.uniform(30, 65),
                throughput=random.uniform(500, 5000),
            ),
        }
        return base.get(asset_type, AssetMetrics())
