# **XOTI: Universal Voice Ordering Assistant for Gulf Countries**

## **Table of Contents**

*   Introduction
*   Scope and Target Audience
*   Functional Requirements
*   Non-Functional Requirements
*   System Architecture
*   Key Components
*   Authentication and Provider Integration Approaches
*   Data Management and Analytics
*   UI/UX Design Considerations
*   Scalability and Deployment Strategy
*   Pros, Cons, and Trade-offs
*   Rough Estimation for 1 Million Users
*   Risks and Mitigation
*   Future Enhancements

## **Introduction**

VoiceHub is a voice-activated universal ordering platform designed to simplify everyday transactions in the Gulf region. Users can speak their requests-such as ordering food, booking a ride, reserving a flight, or purchasing groceries-and the system will interpret the intent, select the appropriate service provider, authenticate seamlessly, and complete the order. The platform leverages advanced voice AI for natural interactions, integrates with regional providers via APIs, and maintains a contextual, adaptive user interface.

The core innovation lies in context-aware automation: the system identifies the service type (e.g., "Order pizza" -> food delivery) and dynamically routes to the best provider based on availability, user preferences, and location. All order history is stored centrally for pattern analysis using machine learning (ML), enabling personalized recommendations.

This document outlines the system design, requirements, architecture, trade-offs, and scalability considerations from a system architect's perspective. It evaluates scenarios like high-traffic peaks, multi-provider failover, and regional compliance.

## **Scope and Target Audience**


*   **Geographic Focus**: Exclusively Gulf Cooperation Council (GCC) countries, including UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, and Oman. Localization for Arabic/English support, currency (AED, SAR, QAR, etc.), and compliance with local regulations (e.g., ZATCA in Saudi Arabia for e-invoicing).
*   **Target Users**: Residents and visitors aged 18+, with access to iOS devices. Initial focus on urban areas (e.g., Dubai, Riyadh, Doha) where delivery/booking services are dense.
*   **Supported Services**: Based on popular regional providers, the platform supports:
    *   Food Delivery (e.g., Talabat, Deliveroo, Careem, Hungerstation)
    *   Grocery Delivery (e.g., InstaShop, Talabat Mart, Nana, Ninja)
    *   Ride-Hailing (e.g., Careem, Uber, Hala Taxi)
    *   Flight Booking (e.g., Almosafer, Rehlat, Wego, Cleartrip)
    *   Hotel Booking (e.g., Almosafer, Booking.com, Wego, Rehlat)
*   **Out of Scope**: Android/web support (Phase 1), international services, physical product sales beyond delivery, real-time video consultations.


## **Functional Requirements**


These define what the system must do, categorized by user journey.

| Category | Requirement | Description |
| --- | --- | --- |
| **Voice Input** | FR-01: Voice Capture | Capture user speech via iOS microphone, stream to LiveKit for real-time processing. Support dialects (Gulf Arabic, English). |
|  | FR-02: Intent Recognition | Use OpenAI Realtime Audio Mini to transcribe, parse intent (e.g., "Book a cab to airport" → ride-hailing, destination). Handle ambiguities with clarification prompts. |
| **Provider Selection** | FR-03: Context-Based Routing | Auto-select provider by service type, user location, ratings, and availability (e.g., nearest Talabat for food). Fallback to user choice. |
|  | FR-04: API Integration | Call provider APIs for search, details, and booking (e.g., Talabat API for menu, Careem for ride quote). |
| **Authentication** | FR-05: User Auth | Support OAuth for providers or universal account login via Apple ID/email. |
|  | FR-06: Order Placement | Complete order with user confirmation (voice/visual). Handle payments via provider or integrated gateway (e.g., Apple Pay). |
| **Order Management** | FR-07: History Tracking | Store order metadata (not sensitive data) in central DB for retrieval and analysis. Pull real-time status from provider APIs. |
| **UI Rendering** | FR-08: Contextual UI | Dynamically render service-specific screens (e.g., food: menu carousel; flight: seat map). Use SwiftUI for native iOS. |
| **Analytics** | FR-09: Pattern Analysis | Aggregate anonymized order data for ML models (e.g., recommend "frequent Uber user → suggest Careem promo"). |
| **Error Handling** | FR-10: Fallbacks | Retry failed API calls, voice re-prompts, or manual UI input. Notify users of outages. |


## **Non-Functional Requirements**

These ensure quality attributes like performance and security.

| Category | Requirement | Description/Metrics |
| --- | --- | --- |
| **Performance** | NFR-01: Latency | End-to-end voice-to-order < 5 seconds (95th percentile). API responses < 2 seconds. |
|  | NFR-02: Availability | 99.9% uptime, with regional redundancy (e.g., AWS Bahrain/Mumbai regions). |
| **Scalability** | NFR-03: Throughput | Handle 100k concurrent sessions; auto-scale for peaks (e.g., weekends in UAE). |
| **Security** | NFR-04: Data Protection | Encrypt voice streams (TLS 1.3); comply with GDPR/PIPA equivalents; no storage of payment details. |
|  | NFR-05: Auth Security | OAuth 2.0 with PKCE; audit logs for all integrations. |
| **Usability** | NFR-06: Accessibility | WCAG 2.1 AA; voice feedback for visually impaired. |
| **Reliability** | NFR-07: Fault Tolerance | Circuit breakers for provider APIs; graceful degradation (e.g., offline mode for history). |
| **Maintainability** | NFR-08: Observability | Centralized logging (e.g., AWS CloudWatch); Rust for backend robustness. |
| **Compliance** | NFR-09: Regional Laws | Support for Arabic RTL; VAT handling; data residency in GCC. |


## **System Architecture**

The architecture is serverless-first, leveraging AWS Lambda for backend logic, Rust for performance-critical components, and LiveKit for voice orchestration. High-level flow:
1.  **User initiates voice session** via iOS app -> Streams to LiveKit agent.
2.  **LiveKit + OpenAI** processes speech -> Extracts intent → Routes to Lambda orchestrator.
3.  **Lambda (Rust)** selects provider, handles auth, calls APIs → Stores metadata in DynamoDB.
4.  **iOS App** renders contextual UI, polls for updates.
5.  **ML Pipeline** (e.g., AWS SageMaker) analyzes stored data offline.
6.  **Microservices**: Separate Lambdas for voice routing, provider integration, and analytics.
7.  **Data Flow**: Event-driven with SQS for queuing API calls; WebSockets via API Gateway for real-time updates.


## **Key Components**

*   **Frontend**: Native iOS (Swift/SwiftUI). Handles voice input (AVFoundation), UI rendering, and API calls to backend.
*   **Voice Agent**: LiveKit for WebRTC-based sessions; OpenAI Realtime Audio Mini embedded for low-latency transcription/STT/TTS.
*   **Backend**: Rust crates (e.g., Tokio for async, Reqwest for HTTP) deployed as Lambda functions. Manages MCP servers (assumed as "Multi-Cloud Provider" or custom; using Lambda for dynamic provisioning).
*   **Database**: DynamoDB for NoSQL order storage; S3 for voice logs (anonymized).
*   **Integrations**: Provider APIs (e.g., Talabat, Careem) via SDKs or REST; OAuth via Auth0 or AWS Cognito.
*   **ML**: AWS SageMaker for pattern analysis (e.g., collaborative filtering on order history).

## **Diagrams**

<img width="2758" height="2829" alt="architecture_diagram_for_xoti" src="https://github.com/user-attachments/assets/096f91ea-99ca-4da9-bd8e-e8bbd99d4904" />

<img width="1921" height="2067" alt="XOTI_aws_c4" src="https://github.com/user-attachments/assets/b49c036c-523c-45ce-bbb7-cd761e0bfe70" />


## **Authentication and Provider Integration Approaches**

Two primary models for provider interactions:

### **Approach 1: Per-Provider OAuth (User Delegates Auth)**

User authenticates directly with each provider (e.g., via app redirect or embedded webview).

**Pros**:

*   Enhanced privacy: No storage of user credentials on our side.
*   Seamless UX for existing users: Leverages provider's login (e.g., one-tap Talabat auth).
*   Lower liability: Orders are placed in user's name; complies with data minimization.
*   Easier compliance: Aligns with OAuth standards, reducing audit burdens.

**Cons**:

*   Friction: Multiple logins for different services (e.g., separate for Careem vs. Almosafer).
*   Token management complexity: Handle refresh tokens, expirations in Lambda.
*   Dependency risks: Provider outages block auth; regional OAuth variations (e.g., Saudi eID integration).
*   Incomplete personalization: Limited access to full user history without consent.

### **Approach 2: Universal Account (Platform-Mediated Orders)**

Users link accounts once; platform stores tokens or places orders on their behalf using a proxy account.

**Pros**:

*   Superior UX: Single VoiceHub login for all services; faster transactions.
*   Centralized control: Easier ML analytics on unified data; auto-fallback between providers.
*   Revenue potential: Add platform fees or bundled deals.
*   Simplified scaling: Fewer auth flows in high-traffic scenarios.

**Cons**:

*   Security risks: Store/manage sensitive tokens; potential for breaches affecting multiple providers.
*   Trust barrier: Users wary of "middleman" for payments/orders; higher churn if issues arise.
*   Legal hurdles: Liability for failed orders; need explicit consents per GCC law (e.g., UAE PDPL).
*   Vendor lock-in: Providers may resist if it bypasses their direct relationship.

**Recommendation**: Hybrid-default to per-provider OAuth for privacy-focused services (e.g., flights), universal for high-frequency (e.g., food/rides). Start with OAuth to build trust, evolve to universal with opt-in.


## **Data Management and Analytics**

*   **Storage**: Capture order metadata (timestamp, service type, provider, amount, items) in DynamoDB. Pull live details (e.g., tracking) from provider APIs on-demand. No PII beyond user ID.
*   **Analytics Pipeline**: Batch jobs (AWS Glue) feed data to SageMaker. Models predict patterns (e.g., "Evening Riyadh users prefer Talabat -> proactive suggestions").
*   **Scenarios**: Real-time (e.g., fraud detection via anomaly scores); batch (weekly reports). Ensure anonymization for GDPR-like compliance.
*   **Better Practices**: Use federated learning to avoid centralizing sensitive data; integrate with provider analytics APIs where available.

## **UI/UX Design Considerations**

*   **Contextual Rendering**: Use a modular SwiftUI framework e.g., FoodView (menu grid), RideView (map integration via MapKit), FlightView (calendar picker). Switch based on intent JSON from backend.
*   **Voice-Visual Sync**: Overlay voice confirmations on UI (e.g., "Confirm pizza order?" with tappable buttons).
*   **Edge Cases**: Offline caching of recent orders; error screens with voice retry.
*   **Best Option**: Native iOS for performance; A/B test Arabic voice prompts for Gulf dialects.


## **Scalability and Deployment Strategy**

*   **AWS Lambda Fit**: Ideal for bursty workloads (e.g., dinner rush). Auto-scales to 1k+ concurrent executions; Rust binaries keep cold starts <100ms.
*   **MCP Servers**: Use Lambda + ECS Fargate for dynamic provisioning—spin up "virtual servers" for heavy ML tasks.
*   **Horizontal Scaling**: API Gateway for throttling; DynamoDB global tables for GCC replication.
*   **Vertical Scaling**: Rust's efficiency handles 10x load without re-arch; monitor via X-Ray.
*   **Scenarios**: Peak (Ramadan): Pre-warm Lambdas; Failover: Multi-region (Bahrain primary, UAE secondary).

**Pros of Lambda+Rust**:

*   Cost-effective: Pay-per-use; Rust reduces compute time by 30-50% vs. Node.js.
*   Scalable: Infinite horizontal; handles 1M users via concurrency.

**Cons**:

*   Cold starts: Mitigate with Provisioned Concurrency.
*   State management: Use external DB/S3; not ideal for long-running voice sessions (offload to LiveKit).


## **Pros, Cons, and Trade-offs**

| Aspect | Pros | Cons | Better Alternative/Trade-off |
| --- | --- | --- | --- |
| **Voice Tech (LiveKit + OpenAI)** | Real-time (<1s latency); scalable WebRTC. | Vendor lock-in; costs ~$0.01/min. | Fallback to Whisper for batch; hybrid with local STT for privacy. |
| **Rust Stack** | Memory-safe, fast; great for API parsing. | Steeper learning curve. | Use for core Lambdas; Python for ML prototyping. |
| **iOS Native** | Optimal performance/battery. | Limits reach (no Android). | Phase 2: React Native for cross-platform. |
| **Provider APIs** | Rich features (e.g., real-time tracking). | Rate limits (e.g., 100/min). | Caching + queuing; partner for higher tiers. |
| **ML Analytics** | Drives retention (personalization). | Data privacy risks. | Opt-in only; edge ML on-device. |

Overall: Serverless excels for variable Gulf traffic (e.g., Hajj peaks).

## **Rough Estimation for 1 Million Users**

**Assuming:**

*   10% daily active users (DAU) = 100k DAU.
*   Average 1 order/DAU/day (voice session ~2min).
*   Each order: 10 API calls (auth + search + book + status pulls).
*   Voice processing: 200k minutes/day.
*   Data: 100k records/day (~1MB/order metadata).

**Resource Estimates**:

*   **Lambda Invocations**: 1M/day (100k orders × 10 calls). At 128MB/500ms, ~$0.20/day (free tier covers initial).
*   **DynamoDB**: 100k writes + 500k reads/day. ~$5/month (provisioned 10 RCU/WCU).
*   **LiveKit/OpenAI**: ~$2k/month (at $0.01/min; scale with reservations).
*   **Storage/ML**: S3 ~$1/month; SageMaker training ~$100/week initially.
*   **Total Monthly Cost**: ~$5-10k at launch, scaling to $50k at full 1M (optimize with caching).
*   **Performance**: Lambda handles 10k concurrent; add $ for concurrency if >1k.
*   **Bottlenecks**: Provider rate limits-mitigate with sharding (e.g., 10 Lambdas per provider).

This is conservative; monitor and right-size post-MVP.


## **Risks and Mitigation**

*   **Risk**: Provider API changes—Mitigation: API wrappers with versioning.
*   **Risk**: Voice accuracy in noisy environments—Mitigation: Noise cancellation + confirmation loops.
*   **Risk**: Regulatory (e.g., Saudi data localization)—Mitigation: AWS GCC regions.
*   **Risk**: Scalability during events (e.g., Dubai Expo)—Mitigation: Auto-scaling policies + load testing.

## **Future Enhancements**

*   Expand to Android/web.
*   Add AR previews (e.g., hotel tours).
*   Integrate blockchain for universal loyalty points.
*   Multi-modal (voice + text/image input).
