-- Manual Database Schema Fix for Membership System
-- Run this SQL script on each tenant database to add missing columns

-- Fix for user_auth_details table - add missing password_hash column
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_1 TIMESTAMP;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_2 TIMESTAMP;
ALTER TABLE user_auth_details ADD COLUMN IF NOT EXISTS last_login_3 TIMESTAMP;

-- Fix for user table - add missing columns
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS membership_type_id INTEGER;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Remove tenant_id columns if they exist (since we use separate databases)
ALTER TABLE "user" DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE user_auth_details DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE attendance_record DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE dues_record DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE referral_record DROP COLUMN IF EXISTS tenant_id;

-- Show the updated schema
\d user_auth_details;
\d "user";
