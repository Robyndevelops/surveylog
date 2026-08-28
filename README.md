# SurveyLog

A multi-tenant digital logbook for student surveyors and their supervisors — track training hours, log entries, and generate progress reports toward professional certification.

Started as a generalized version of a single-supervisor logbook system, rebuilt to support multiple independent student/supervisor pairs with configurable settings (branding, job types, hour targets, report sections) per pair.

## Structure
- `app.py` — Flask PDF generation server (deployed on Railway)
- Frontend and database schema to follow

## Status
Early setup — genericizing the original single-tenant codebase for multi-tenant use.
