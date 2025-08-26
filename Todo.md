Todo: 
(Completed marked with [x])

1. LANDING PAGE [x]
    Set up simple landing page [x]
    Create email signup for waitlist [x]
    Implement API to add emails to mailgun [x]
    Add Umami analytics []
2. INITIAL BACKEND []
    2.1 DATABASE [] 
        Set up database []
            Prepare for RLS policies []
            Prepare for secure connections from web app []
            Prepare tables and columns for data []
                Users []
                    username
                    email
                    orgs (all organizations the user is a member of by ID)
                    proposals (all proposals the user has created by ID)
                    shared_proposals (all proposals shared with the user by ID)
                    subscription tier (free, pro, enterprise)
                    payment_frequency (monthly, annually)
                    last_payment (YYYY-MM-DD)
                    billing_period_ends (end of current billing period)
                Organizations (tied to admin user, with "org_users" supporting additional users) []
                    users (all users in the org by ID)
                    proposals (all proposals in the org by ID)
                    admin (admin user ID)
                    subscription tier (free, pro, enterprise, by admin user's subscription plan)
                    description (optional) -- description of the org
                    files (optional) -- frequently used files by the org
                Proposals (tied to users and orgs, with org admins having access to all proposals within their org) []
                    ID (unique)
                    user (user ID)
                    org (org ID)
                    shared_with (users the proposal is shared with by ID)
                    state (draft, finalized)
                    last_edited (last edit YYYY-MM-DD HH:MM)
                    downloads (number of times downloaded)'
            Test database []
                Test RLS policies []
                Test secure connections from web app []
                Test data []
            SECURITY AUDIT []
    2.2 USERS
        Set up user account functionality []
            Oauth signup/signin []
            Roles (admin, user, guest) []
            Edit profile (email, name) []
            Create/edit organizations, transfer ownership of organizations []
            Proposals tied to userID & organizationID []
            Organizations tied to userID with admins and users []
            Sharing of proposals within organizations (admins have universal access within their org) []
            Subscription (upgrade/downgrade/cancel subscriptions. in case of cancellation, both user and any orgs they are admin of must be downgraded at the end of billing period) -- integrated with Stripe []
            (For admins) Add/remove/change roles of users within organizations []
            Delete organization [] (proposals should remain tied to userIDs)
            Delete proposals []
        Test user functionality []
            Test profile changes []
            Test role-based access []
            Test organization edits []
            Test sharing of proposals []
            Test transfering organization owner []
            Test whether changes reflect in database []
        SECURITY AUDIT []
    2.3 BILLING
        Set up billing with Stripe []
            Integrate Stripe into back-end and database []
            Set up coupon code functionality to offer users free or discounted plans at our discretion []
            Test payment []
            Test cancellation []
            Test coupon codes []
            Test subscription management via user panel []
        SECURITY AUDIT []
    2.4 AI
        Set up AI []
            Set up RAG with organized proposal templates and samples for AI []
            Set up API calls to AI []
            Train AI on RAG usage and optimize prompts and create most cost-effective workflow []
            Begin testing AI []
        SECURITY AUDIT []
    2.5 TRANSFORMERS
        Set up file export []
            Export to .md []
            Export to .docx []
            Export to .pdf []
        Test file export in all formats []
        Test if database updates correctly []
        SECURITY AUDIT []
3. FRONTEND []
    3.1 USER PANEL []
        Create login page []
        Stylize user panel []
            Add "My proposals" overview []
            Add "My organizations" overview with user role listed per org []
            Add other functionality like "create new org" or editing user profile front-ends []
    3.2 PROPOSAL FORM []
        Implement SurveyJS []
        Set up form for proposals []
        Integrate API calls and form interactivity []
            Initial request for information []
            (Via planner AI) Dynamic structuring of form to fit intended proposal structure []
            API call to creative writer AI and response parsing []
            User review of section (approval/edits) []
            Re-call of API to implement potential edits []
            User approval of section []
            Saving state to database []
            Next request for information (according to Planner's section structure) []
            Finalization message when last section done []
            Export integration []
        SECURITY AUDIT []
    3.3 ADDITIONAL FUNCTIONALITY []
        Implement paywall if user hits limit for plan []
        Implement CTAs for upgrading []
        Implement basic forum functionality []
    4. TESTING GO LIVE []