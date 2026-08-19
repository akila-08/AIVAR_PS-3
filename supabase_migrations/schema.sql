create table public.policies (
    rule_id text primary key,
    tool text not null,
    condition text,
    action text not null,
    reason text not null default ''
);

create table public.audit_log (
    action_id uuid primary key,
    created_at timestamptz not null default now(),
    tool text not null,
    params jsonb not null default '{}'::jsonb,
    outcome text not null,
    matched_rule text,
    reason text not null default '',
    executed boolean not null default false,
    module text not null default 'guardrail'
);

create index audit_log_created_at_idx on public.audit_log (created_at desc);

create table public.reviews (
    review_id uuid primary key,
    created_at timestamptz not null default now(),
    status text not null check (status in ('pending', 'approved', 'denied')),
    action jsonb not null,
    reason text not null default '',
    expires_at bigint not null
);

alter table public.policies enable row level security;
alter table public.audit_log enable row level security;
alter table public.reviews enable row level security;


