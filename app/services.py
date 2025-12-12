# app/services.py
"""
Class-based service layer for organization management.
Provides better encapsulation, testability, and follows SOLID principles.

Architecture:
- DatabaseConnectionManager: Handles multi-tenant database connections
- OrganizationService: Business logic for organization CRUD operations
- MigrationService: Handles large-scale data migrations with progress tracking
"""
from typing import Optional, Dict, Any, AsyncGenerator
from bson.objectid import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, OperationFailure
from app.db import master_db, client as default_client
from app.utils import slugify
from app.auth import hash_password, verify_password
from app.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# DATABASE CONNECTION MANAGER
# ============================================================================

class DatabaseConnectionManager:
    """
    Manages database connections for multi-tenant architecture.
    Implements connection pooling and caching for optimal performance.
    """
    
    def __init__(self):
        self._tenant_clients: Dict[str, AsyncIOMotorClient] = {}
        self._default_client = default_client
        self._master_db = master_db
        self._connection_timeout = 5000  # milliseconds
        logger.info("database_connection_manager_initialized")
    
    def get_tenant_db(self, org_doc: dict) -> AsyncIOMotorDatabase:
        """
        Get the appropriate database connection for a tenant.
        Returns either a dedicated DB connection or the shared master_db.
        
        Args:
            org_doc: Organization document from master collection
            
        Returns:
            AsyncIOMotorDatabase instance for the tenant
        """
        db_type = org_doc.get("db_type", "shared")
        
        if db_type == "dedicated":
            db_uri = org_doc.get("connection_details", {}).get("db_uri")
            db_name = org_doc.get("connection_details", {}).get("db_name")
            
            if db_uri and db_name:
                cache_key = f"{db_uri}_{db_name}"
                
                # Create new connection if not cached
                if cache_key not in self._tenant_clients:
                    logger.info(
                        "creating_new_tenant_connection",
                        db_name=db_name,
                        db_type="dedicated"
                    )
                    self._tenant_clients[cache_key] = AsyncIOMotorClient(
                        db_uri,
                        serverSelectionTimeoutMS=self._connection_timeout,
                        maxPoolSize=50,  # Connection pool size
                        minPoolSize=10
                    )
                
                return self._tenant_clients[cache_key][db_name]
        
        # Default: use shared database
        db_name = org_doc.get("db_name", "master_db")
        return self._default_client[db_name]
    
    async def test_connection(self, db_uri: str, db_name: str) -> bool:
        """
        Test a database connection without caching it.
        
        Args:
            db_uri: MongoDB connection URI
            db_name: Database name
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_client = AsyncIOMotorClient(
                db_uri,
                serverSelectionTimeoutMS=self._connection_timeout
            )
            await test_client[db_name].command('ping')
            test_client.close()
            logger.info("database_connection_test_successful", db_name=db_name)
            return True
        except Exception as e:
            logger.error(
                "database_connection_test_failed",
                db_name=db_name,
                error=str(e)
            )
            return False
    
    async def close_all_connections(self) -> None:
        """Close all tenant database connections gracefully."""
        for cache_key, client in self._tenant_clients.items():
            try:
                client.close()
                logger.debug("tenant_connection_closed", cache_key=cache_key)
            except Exception as e:
                logger.warning(
                    "error_closing_tenant_connection",
                    cache_key=cache_key,
                    error=str(e)
                )
        
        self._tenant_clients.clear()
        logger.info(
            "all_tenant_connections_closed",
            count=len(self._tenant_clients)
        )
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about current connections."""
        return {
            "total_connections": len(self._tenant_clients),
            "connection_keys": list(self._tenant_clients.keys())
        }


# ============================================================================
# MIGRATION SERVICE
# ============================================================================

class MigrationService:
    """
    Handles large-scale data migrations with progress tracking.
    Used for renaming organizations with large datasets.
    """
    
    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db_manager = db_manager
        self.batch_size = 1000  # Documents per batch
        logger.info("migration_service_initialized", batch_size=self.batch_size)
    
    async def migrate_collection_with_progress(
        self,
        source_db: AsyncIOMotorDatabase,
        source_collection: str,
        target_collection: str,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Migrate documents from source to target collection with progress tracking.
        
        Args:
            source_db: Source database
            source_collection: Source collection name
            target_collection: Target collection name
            callback: Optional callback function for progress updates
            
        Returns:
            Migration statistics dictionary
        """
        logger.info(
            "starting_collection_migration",
            source=source_collection,
            target=target_collection
        )
        
        src_coll = source_db[source_collection]
        dst_coll = source_db[target_collection]
        
        # Get total document count
        total_docs = await src_coll.count_documents({})
        migrated_docs = 0
        failed_docs = 0
        batch_buffer = []
        
        logger.info("migration_document_count", total=total_docs)
        
        try:
            # Stream documents in batches
            async for document in src_coll.find({}):
                document.pop("_id", None)  # Remove _id for reinsertion
                batch_buffer.append(document)
                
                # Insert batch when buffer is full
                if len(batch_buffer) >= self.batch_size:
                    try:
                        await dst_coll.insert_many(batch_buffer, ordered=False)
                        migrated_docs += len(batch_buffer)
                        
                        # Progress callback
                        if callback:
                            await callback(migrated_docs, total_docs)
                        
                        logger.debug(
                            "migration_batch_completed",
                            migrated=migrated_docs,
                            total=total_docs,
                            progress_pct=round((migrated_docs / total_docs) * 100, 2)
                        )
                        
                        batch_buffer.clear()
                    except Exception as e:
                        logger.error(
                            "migration_batch_failed",
                            error=str(e),
                            batch_size=len(batch_buffer)
                        )
                        failed_docs += len(batch_buffer)
                        batch_buffer.clear()
            
            # Insert remaining documents
            if batch_buffer:
                try:
                    await dst_coll.insert_many(batch_buffer, ordered=False)
                    migrated_docs += len(batch_buffer)
                except Exception as e:
                    logger.error("migration_final_batch_failed", error=str(e))
                    failed_docs += len(batch_buffer)
            
            migration_stats = {
                "total_documents": total_docs,
                "migrated_documents": migrated_docs,
                "failed_documents": failed_docs,
                "success_rate": round((migrated_docs / total_docs) * 100, 2) if total_docs > 0 else 0
            }
            
            logger.info(
                "collection_migration_completed",
                **migration_stats
            )
            
            return migration_stats
            
        except Exception as e:
            logger.error(
                "collection_migration_failed",
                source=source_collection,
                target=target_collection,
                error=str(e)
            )
            raise


# ============================================================================
# ORGANIZATION SERVICE
# ============================================================================

class OrganizationService:
    """
    Service class for organization CRUD operations.
    Implements business logic with proper error handling and logging.
    """
    
    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db_manager = db_manager
        self.migration_service = MigrationService(db_manager)
        self.org_collection: AsyncIOMotorCollection = master_db["organizations"]
        logger.info("organization_service_initialized")
    
    async def ensure_indexes(self) -> None:
        """Create database indexes for optimal performance and data integrity."""
        try:
            # Unique index on organization_name
            await self.org_collection.create_index(
                "organization_name",
                unique=True,
                name="idx_organization_name_unique"
            )
            
            # Unique index on admin.email
            await self.org_collection.create_index(
                "admin.email",
                unique=True,
                name="idx_admin_email_unique"
            )
            
            # Index on created_at for sorting
            await self.org_collection.create_index(
                "created_at",
                name="idx_created_at"
            )
            
            # Index on db_type for filtering
            await self.org_collection.create_index(
                "db_type",
                name="idx_db_type"
            )
            
            logger.info("database_indexes_created_successfully")
        except Exception as e:
            logger.error("failed_to_create_indexes", error=str(e))
            raise
    
    async def organization_exists(self, name: str) -> bool:
        """
        Check if an organization exists by name.
        
        Args:
            name: Organization name to check
            
        Returns:
            True if organization exists, False otherwise
        """
        exists = await self.org_collection.find_one({"organization_name": name}) is not None
        logger.debug("organization_existence_check", org_name=name, exists=exists)
        return exists
    
    async def create_organization(
        self,
        org_name: str,
        admin_email: str,
        admin_password: str,
        db_uri: Optional[str] = None,
        db_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new organization with metadata and dynamic collection/database.
        
        Args:
            org_name: Organization name
            admin_email: Admin email address
            admin_password: Admin password (will be hashed)
            db_uri: Optional MongoDB URI for dedicated database
            db_name: Optional database name for dedicated mode
            
        Returns:
            Dictionary containing organization details
            
        Raises:
            ValueError: If organization exists or connection fails
            DuplicateKeyError: If duplicate name or email
        """
        logger.info(
            "creating_organization",
            org_name=org_name,
            admin_email=admin_email,
            db_type="dedicated" if db_uri else "shared"
        )
        
        slug = slugify(org_name)
        collection_name = f"org_{slug}"
        
        # Prepare admin document
        admin_doc = {
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": "admin",
            "created_at": datetime.utcnow(),
        }
        
        # Prepare organization metadata
        org_metadata = {
            "organization_name": org_name,
            "collection_name": collection_name,
            "admin": admin_doc,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "active"
        }
        
        # Handle dedicated database mode
        if db_uri and db_name:
            # Test connection first
            connection_valid = await self.db_manager.test_connection(db_uri, db_name)
            if not connection_valid:
                raise ValueError(
                    f"Failed to connect to dedicated database. "
                    f"Please verify the connection URI and credentials."
                )
            
            org_metadata["db_type"] = "dedicated"
            org_metadata["connection_details"] = {
                "db_uri": db_uri,  # TODO: Encrypt in production
                "db_name": db_name
            }
            org_metadata["db_name"] = db_name
            
            try:
                # Initialize collection in dedicated database
                tenant_client = AsyncIOMotorClient(
                    db_uri,
                    serverSelectionTimeoutMS=5000
                )
                tenant_db = tenant_client[db_name]
                col = tenant_db[collection_name]
                
                # Create collection with initialization document
                await col.insert_one({"_init": True, "created_at": datetime.utcnow()})
                await col.delete_many({"_init": True})
                
                # Create indexes in tenant collection
                await col.create_index("created_at")
                
                tenant_client.close()
                
                logger.info(
                    "dedicated_database_initialized",
                    org_name=org_name,
                    db_name=db_name,
                    collection=collection_name
                )
            except Exception as e:
                logger.error(
                    "dedicated_database_initialization_failed",
                    org_name=org_name,
                    error=str(e)
                )
                raise ValueError(f"Failed to initialize dedicated database: {str(e)}")
        else:
            # Shared database mode (default)
            org_metadata["db_type"] = "shared"
            org_metadata["db_name"] = "master_db"
            
            # Create collection in master_db
            col = master_db[collection_name]
            await col.insert_one({"_init": True, "created_at": datetime.utcnow()})
            await col.delete_many({"_init": True})
            
            # Create indexes
            await col.create_index("created_at")
            
            logger.info(
                "shared_collection_initialized",
                org_name=org_name,
                collection=collection_name
            )
        
        # Insert organization metadata
        try:
            res = await self.org_collection.insert_one(org_metadata)
            org_id = str(res.inserted_id)
            
            logger.info(
                "organization_created_successfully",
                org_id=org_id,
                org_name=org_name,
                db_type=org_metadata["db_type"]
            )
            
            return {
                "organization_name": org_name,
                "collection_name": collection_name,
                "admin_email": admin_email,
                "id": org_id,
                "db_type": org_metadata["db_type"],
                "db_name": org_metadata.get("db_name"),
                "created_at": org_metadata["created_at"].isoformat()
            }
            
        except DuplicateKeyError as e:
            logger.warning(
                "duplicate_organization_creation_attempt",
                org_name=org_name,
                admin_email=admin_email,
                error=str(e)
            )
            
            # Cleanup: remove created collection
            if org_metadata["db_type"] == "shared":
                await master_db.drop_collection(collection_name)
            
            # Provide specific error message
            if "organization_name" in str(e):
                raise ValueError(f"Organization '{org_name}' already exists")
            elif "admin.email" in str(e):
                raise ValueError(f"Admin email '{admin_email}' is already registered")
            else:
                raise ValueError("Duplicate organization or admin email")
    
    async def get_organization(self, org_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve organization metadata by name.
        
        Args:
            org_name: Organization name
            
        Returns:
            Organization document or None if not found
        """
        doc = await self.org_collection.find_one({"organization_name": org_name})
        
        if doc:
            # Convert ObjectId to string
            doc["_id"] = str(doc["_id"])
            
            # Convert datetime to ISO format
            if "created_at" in doc:
                doc["created_at"] = doc["created_at"].isoformat()
            if "updated_at" in doc:
                doc["updated_at"] = doc["updated_at"].isoformat()
            if "admin" in doc and "created_at" in doc["admin"]:
                doc["admin"]["created_at"] = doc["admin"]["created_at"].isoformat()
            
            logger.debug("organization_retrieved", org_name=org_name)
        else:
            logger.warning("organization_not_found", org_name=org_name)
        
        return doc
    
    async def update_organization(
        self,
        org_name: str,
        new_org_name: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        db_uri: Optional[str] = None,
        db_name: Optional[str] = None
    ) -> bool:
        """
        Update organization metadata with atomic rename support.
        Uses renameCollection for same-DB renames, document copy for cross-DB.
        
        For large datasets (>10,000 documents), uses background migration with progress tracking.
        
        Args:
            org_name: Current organization name
            new_org_name: New organization name (optional)
            email: New admin email (optional)
            password: New admin password (optional)
            db_uri: New database URI (optional)
            db_name: New database name (optional)
            
        Returns:
            True if update successful
            
        Raises:
            ValueError: If organization not found or update fails
            DuplicateKeyError: If new name already exists
        """
        logger.info(
            "updating_organization",
            org_name=org_name,
            new_org_name=new_org_name,
            email=email,
            password_change=password is not None
        )
        
        doc = await self.org_collection.find_one({"organization_name": org_name})
        if not doc:
            logger.error("update_failed_org_not_found", org_name=org_name)
            raise ValueError(f"Organization '{org_name}' not found")
        
        updates = {}
        current_db = self.db_manager.get_tenant_db(doc)
        
        # Handle organization name change (collection rename)
        if new_org_name and new_org_name != org_name:
            new_slug = slugify(new_org_name)
            new_collection_name = f"org_{new_slug}"
            old_collection_name = doc["collection_name"]
            
            # Check if we're in the same database
            same_db = doc.get("db_type", "shared") == "shared"
            
            # Get document count to determine migration strategy
            old_coll = current_db[old_collection_name]
            doc_count = await old_coll.count_documents({})
            
            logger.info(
                "collection_rename_required",
                old_name=old_collection_name,
                new_name=new_collection_name,
                document_count=doc_count,
                same_db=same_db
            )
            
            if same_db and doc_count < 10000:
                # Attempt atomic rename for small collections in same DB
                try:
                    await current_db.command(
                        "renameCollection",
                        f"{current_db.name}.{old_collection_name}",
                        to=f"{current_db.name}.{new_collection_name}",
                        dropTarget=False
                    )
                    logger.info(
                        "collection_renamed_atomically",
                        old_name=old_collection_name,
                        new_name=new_collection_name
                    )
                except OperationFailure as e:
                    # Fallback to document copy if renameCollection fails
                    logger.warning(
                        "atomic_rename_failed_using_fallback",
                        error=str(e),
                        org_name=org_name
                    )
                    await self._copy_collection_documents(
                        current_db,
                        old_collection_name,
                        new_collection_name
                    )
                    await current_db.drop_collection(old_collection_name)
            elif doc_count >= 10000:
                # Use background migration for large datasets
                logger.info(
                    "using_background_migration_for_large_dataset",
                    document_count=doc_count
                )
                migration_stats = await self.migration_service.migrate_collection_with_progress(
                    current_db,
                    old_collection_name,
                    new_collection_name
                )
                await current_db.drop_collection(old_collection_name)
                logger.info("large_dataset_migration_completed", **migration_stats)
            else:
                # Cross-database migration: copy documents
                await self._copy_collection_documents(
                    current_db,
                    old_collection_name,
                    new_collection_name
                )
                await current_db.drop_collection(old_collection_name)
                logger.info(
                    "collection_migrated_cross_database",
                    org_name=org_name,
                    new_org_name=new_org_name
                )
            
            updates["organization_name"] = new_org_name
            updates["collection_name"] = new_collection_name
        
        # Handle admin updates
        if email or password:
            admin = doc["admin"].copy()
            if email:
                admin["email"] = email
                logger.info("admin_email_updated", org_name=org_name, new_email=email)
            if password:
                admin["password_hash"] = hash_password(password)
                logger.info("admin_password_updated", org_name=org_name)
            updates["admin"] = admin
        
        # Handle database connection updates
        if db_uri or db_name:
            connection_details = doc.get("connection_details", {}).copy()
            
            if db_uri:
                # Test new connection
                test_db_name = db_name or connection_details.get("db_name", "master_db")
                connection_valid = await self.db_manager.test_connection(db_uri, test_db_name)
                
                if not connection_valid:
                    raise ValueError("Failed to connect with provided database URI")
                
                connection_details["db_uri"] = db_uri
                updates["db_type"] = "dedicated"
                logger.info("database_uri_updated", org_name=org_name)
            
            if db_name:
                connection_details["db_name"] = db_name
                updates["db_name"] = db_name
                logger.info("database_name_updated", org_name=org_name, db_name=db_name)
            
            if connection_details:
                updates["connection_details"] = connection_details
        
        # Apply updates
        if updates:
            updates["updated_at"] = datetime.utcnow()
            
            try:
                result = await self.org_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": updates}
                )
                
                if result.modified_count > 0:
                    logger.info(
                        "organization_updated_successfully",
                        org_name=org_name,
                        updates=list(updates.keys())
                    )
                else:
                    logger.warning(
                        "organization_update_no_changes",
                        org_name=org_name
                    )
                
                return True
                
            except DuplicateKeyError:
                logger.error(
                    "update_failed_duplicate_name",
                    new_org_name=new_org_name
                )
                raise ValueError(f"Organization '{new_org_name}' already exists")
        else:
            logger.info("no_updates_required", org_name=org_name)
            return True
    
    async def _copy_collection_documents(
        self,
        db: AsyncIOMotorDatabase,
        source_collection: str,
        target_collection: str
    ) -> None:
        """
        Copy documents from source to target collection.
        For large datasets, prefer using MigrationService.
        
        Args:
            db: Database instance
            source_collection: Source collection name
            target_collection: Target collection name
        """
        src_coll = db[source_collection]
        dst_coll = db[target_collection]
        
        doc_count = 0
        batch_size = 500
        batch_buffer = []
        
        async for item in src_coll.find({}):
            item.pop("_id", None)
            batch_buffer.append(item)
            
            if len(batch_buffer) >= batch_size:
                await dst_coll.insert_many(batch_buffer, ordered=False)
                doc_count += len(batch_buffer)
                batch_buffer.clear()
        
        # Insert remaining documents
        if batch_buffer:
            await dst_coll.insert_many(batch_buffer, ordered=False)
            doc_count += len(batch_buffer)
        
        logger.info(
            "collection_documents_copied",
            source=source_collection,
            target=target_collection,
            count=doc_count
        )
    
    async def delete_organization(self, org_name: str) -> bool:
        """
        Delete organization and associated collection/database.
        
        Args:
            org_name: Organization name to delete
            
        Returns:
            True if deleted, False if not found
        """
        logger.info("deleting_organization", org_name=org_name)
        
        doc = await self.org_collection.find_one_and_delete(
            {"organization_name": org_name}
        )
        
        if not doc:
            logger.warning("delete_failed_org_not_found", org_name=org_name)
            return False
        
        colname = doc["collection_name"]
        db_type = doc.get("db_type", "shared")
        
        # Drop collection based on database type
        try:
            if db_type == "shared":
                if colname in await master_db.list_collection_names():
                    await master_db.drop_collection(colname)
                    logger.info("shared_collection_dropped", collection=colname)
            else:
                tenant_db = self.db_manager.get_tenant_db(doc)
                if tenant_db and colname in await tenant_db.list_collection_names():
                    await tenant_db.drop_collection(colname)
                    logger.info(
                        "dedicated_collection_dropped",
                        collection=colname,
                        db_type=db_type
                    )
        except Exception as e:
            logger.error(
                "error_dropping_collection",
                collection=colname,
                error=str(e)
            )
        
        logger.info("organization_deleted_successfully", org_name=org_name)
        return True
    
    async def authenticate_admin(
        self,
        email: str,
        password: str
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate admin by email and password.
        
        Args:
            email: Admin email address
            password: Admin password
            
        Returns:
            Admin/org info dict if successful, None otherwise
        """
        logger.info("admin_authentication_attempt", email=email)
        
        doc = await self.org_collection.find_one({"admin.email": email})
        if not doc:
            logger.warning("authentication_failed_email_not_found", email=email)
            return None
        
        admin = doc["admin"]
        
        if verify_password(password, admin["password_hash"]):
            logger.info(
                "admin_authenticated_successfully",
                email=email,
                org_id=str(doc["_id"]),
                org_name=doc["organization_name"]
            )
            
            return {
                "org_id": str(doc["_id"]),
                "org_name": doc["organization_name"],
                "admin_email": admin["email"],
                "collection_name": doc["collection_name"],
                "db_type": doc.get("db_type", "shared"),
                "db_name": doc.get("db_name", "master_db")
            }
        
        logger.warning("authentication_failed_invalid_password", email=email)
        return None
    
    async def get_organization_stats(self) -> Dict[str, Any]:
        """
        Get statistics about all organizations.
        
        Returns:
            Dictionary with organization statistics
        """
        total_orgs = await self.org_collection.count_documents({})
        shared_orgs = await self.org_collection.count_documents({"db_type": "shared"})
        dedicated_orgs = await self.org_collection.count_documents({"db_type": "dedicated"})
        
        stats = {
            "total_organizations": total_orgs,
            "shared_database_orgs": shared_orgs,
            "dedicated_database_orgs": dedicated_orgs,
            "connection_stats": self.db_manager.get_connection_stats()
        }
        
        logger.debug("organization_stats_retrieved", **stats)
        return stats


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Global instances (initialized once, reused throughout the application)
db_connection_manager = DatabaseConnectionManager()
organization_service = OrganizationService(db_connection_manager)
