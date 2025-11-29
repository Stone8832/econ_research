from otree.api import (
    Currency,
    cu,
    currency_range,
    models,
    widgets,
    BaseConstants,
    BaseSubsession,
    BaseGroup,
    BasePlayer,
    ExtraModel,
    WaitPage,
    Page,
    read_csv,
)

import units
import shared_out


doc = 'Public good provision with endogenous/exogenous firms and constant/increasing returns.'


class C(BaseConstants):
    NAME_IN_URL = 'public_goods_firms'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 30
    MAX_FIRM_SIZE = 6
    EFFORT_ENDOWMENT = 8
    ROUNDS_PER_FIRM = 10


class Subsession(BaseSubsession):
    formation_type = models.StringField()
    returns_type = models.StringField()


class Group(BaseGroup):
    period_index = models.IntegerField()


class Player(BasePlayer):
    effort_to_firm = models.IntegerField(min=0, max=C.EFFORT_ENDOWMENT)
    effort_to_self = models.IntegerField()
    firm_id = models.IntegerField()
    is_firm_owner = models.IntegerField(initial=0)
    firm_size = models.IntegerField()
    firm_total_effort = models.FloatField()
    firm_per_capita_effort = models.FloatField()
    firm_per_capita_payoff = models.FloatField()
    autarkic = models.IntegerField(initial=0)
    proposed_firm = models.IntegerField(label='Firm you wish to work for (0 = work alone)', min=0)


# ---------------------------------------------------------------------------
# Session setup helpers
# ---------------------------------------------------------------------------

def creating_session(subsession: Subsession):
    session = subsession.session
    formation_type = session.config['formation_type']
    returns_type = session.config['returns_type']

    for s in subsession.in_all_rounds():
        s.formation_type = formation_type
        s.returns_type = returns_type

    # store period index on group (1..NUM_ROUNDS)
    for g in subsession.get_groups():
        g.period_index = subsession.round_number

    if formation_type == 'exogenous' and subsession.round_number == 1:
        session.vars['exo_group_matrices'] = build_exogenous_matrices(subsession)


def build_exogenous_matrices(subsession: Subsession):
    """Create a deterministic schedule of exogenous firm assignments.

    Players rotate across firm sizes (2, 3, 4, 5, 6) every 10 rounds so that
    everyone experiences multiple sizes during the session.
    """

    players = subsession.get_players()
    num_players = len(players)
    size_pattern = [2, 3, 4, 5, 6]
    if sum(size_pattern) != num_players:
        # fallback: single firm containing everyone
        return [[list(range(1, num_players + 1))] for _ in range(C.NUM_ROUNDS)]

    matrices = []
    player_ids = [p.id_in_subsession for p in players]

    for block in range(C.NUM_ROUNDS // C.ROUNDS_PER_FIRM):
        # simple rotation of player order each block
        rotated = player_ids[block:] + player_ids[:block]
        idx = 0
        block_matrix = []
        for size in size_pattern:
            block_matrix.append(rotated[idx : idx + size])
            idx += size
        for _ in range(C.ROUNDS_PER_FIRM):
            matrices.append(block_matrix)
    return matrices


# ---------------------------------------------------------------------------
# Payoff helpers
# ---------------------------------------------------------------------------

def mpcr_linear(n):
    mpcr_by_n = {
        2: 0.65,
        3: 0.55,
        4: 0.49,
        5: 0.45,
        6: 0.42,
    }
    return mpcr_by_n.get(n, 0)


def production_increasing(E):
    # f(E) = a * E^b with calibration from design
    if E <= 0:
        return 0.0
    a = 0.2496
    b = 1.5952
    return a * (E ** b)


# ---------------------------------------------------------------------------
# Firm formation
# ---------------------------------------------------------------------------

def set_firms_exogenous(subsession: Subsession):
    session = subsession.session
    matrices = session.vars['exo_group_matrices']
    matrix = matrices[subsession.round_number - 1]
    subsession.set_group_matrix(matrix)

    for group in subsession.get_groups():
        owner_id = group.get_players()[0].id_in_subsession
        for p in group.get_players():
            p.firm_id = owner_id
            p.is_firm_owner = 1 if p.id_in_subsession == owner_id else 0


def assign_endogenous_firms(subsession: Subsession):
    players = sorted(subsession.get_players(), key=lambda p: p.id_in_subsession)
    firms = {p.id_in_subsession: [] for p in players}

    for p in players:
        target = p.proposed_firm or 0
        if target == 0 or target not in firms:
            continue
        if len(firms[target]) < C.MAX_FIRM_SIZE:
            firms[target].append(p)

    for owner_id, members in firms.items():
        if not members:
            continue
        owner = next(p for p in players if p.id_in_subsession == owner_id)
        full_members = [owner] + [m for m in members if m != owner]
        for m in full_members:
            m.firm_id = owner_id
            m.is_firm_owner = 1 if m.id_in_subsession == owner_id else 0

    for p in players:
        if not p.firm_id:
            p.autarkic = 1
            p.is_firm_owner = 0


# ---------------------------------------------------------------------------
# Payoffs
# ---------------------------------------------------------------------------

def set_payoffs(subsession: Subsession):
    returns_type = subsession.returns_type
    players = subsession.get_players()

    firms = {}
    for p in players:
        if p.firm_id:
            firms.setdefault(p.firm_id, []).append(p)

    # autarky players get full endowment to self
    for p in players:
        if not p.firm_id:
            p.autarkic = 1
            p.effort_to_firm = 0
            p.effort_to_self = C.EFFORT_ENDOWMENT
            p.payoff = C.EFFORT_ENDOWMENT

    for fid, members in firms.items():
        n = len(members)
        total_effort = sum(m.effort_to_firm or 0 for m in members)

        if returns_type == 'constant':
            alpha = mpcr_linear(n)
            total_output = alpha * n * total_effort
        else:
            total_output = production_increasing(total_effort)

        per_capita_output = total_output / n if n > 0 else 0

        for m in members:
            m.autarkic = 0
            m.firm_size = n
            m.firm_total_effort = total_effort
            m.firm_per_capita_effort = total_effort / n if n > 0 else 0
            m.firm_per_capita_payoff = per_capita_output
            if m.effort_to_self is None:
                m.effort_to_self = C.EFFORT_ENDOWMENT - (m.effort_to_firm or 0)
            m.payoff = m.effort_to_self + per_capita_output


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class Instructions(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1


class FirmFormation(Page):
    form_model = 'player'
    form_fields = ['proposed_firm']
    timeout_seconds = 120

    @staticmethod
    def is_displayed(player: Player):
        return player.subsession.formation_type == 'endogenous'

    @staticmethod
    def vars_for_template(player: Player):
        players = player.subsession.get_players()
        history = []
        for p in players:
            rows = []
            for past in p.in_previous_rounds():
                rows.append(
                    dict(
                        round=past.round_number,
                        firm=past.firm_id or 'Autarky',
                        effort=past.effort_to_firm if past.effort_to_firm is not None else '-',
                        per_capita_payoff=past.firm_per_capita_payoff if past.firm_per_capita_payoff is not None else '-',
                    )
                )
            history.append(dict(player=p.id_in_subsession, rows=rows))

        return dict(
            max_firm_size=C.MAX_FIRM_SIZE,
            players=players,
            history=history,
        )


class FormationWait(WaitPage):
    wait_for_all_groups = True

    @staticmethod
    def after_all_players_arrive(subsession: Subsession):
        for p in subsession.get_players():
            p.firm_id = None
            p.autarkic = 0
            p.is_firm_owner = 0

        if subsession.formation_type == 'exogenous':
            set_firms_exogenous(subsession)
        else:
            assign_endogenous_firms(subsession)


class EffortDecision(Page):
    timeout_seconds = 60

    @staticmethod
    def get_form_fields(player: Player):
        return ['effort_to_firm'] if player.firm_id else []

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            endowment=C.EFFORT_ENDOWMENT,
            in_firm=bool(player.firm_id),
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if not player.firm_id:
            player.effort_to_firm = 0
            player.effort_to_self = C.EFFORT_ENDOWMENT
            return

        if player.effort_to_firm is None:
            player.effort_to_firm = 0
        if player.effort_to_firm < 0 or player.effort_to_firm > C.EFFORT_ENDOWMENT:
            raise ValueError('effort_to_firm out of bounds')
        player.effort_to_self = C.EFFORT_ENDOWMENT - player.effort_to_firm


class ResultsWait(WaitPage):
    wait_for_all_groups = True

    @staticmethod
    def after_all_players_arrive(subsession: Subsession):
        set_payoffs(subsession)


class ResultsPeriod(Page):
    timeout_seconds = 30

    @staticmethod
    def vars_for_template(player: Player):
        subsession = player.subsession
        players = subsession.get_players()

        firms = {}
        for p in players:
            fid = p.firm_id
            if not fid:
                continue
            d = firms.setdefault(fid, dict(size=0, total_effort=0, per_capita_effort=0, per_capita_payoff=0))
            d['total_effort'] += p.effort_to_firm or 0
            d['size'] += 1
            d['per_capita_payoff'] = p.firm_per_capita_payoff or 0

        for fid, d in firms.items():
            n = d['size']
            d['per_capita_effort'] = d['total_effort'] / n if n > 0 else 0

        firm_list = [dict(firm_id=fid, **d) for fid, d in sorted(firms.items())]

        return dict(
            firm_list=firm_list,
            autarkic=player.autarkic,
            effort_to_firm=player.effort_to_firm,
            effort_to_self=player.effort_to_self,
            payoff=player.payoff,
            firm_id=player.firm_id,
        )


class FinalResults(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player: Player):
        all_players = player.in_all_rounds()
        points = sum(p.payoff for p in all_players)

        return dict(
            total_points=points,
            total_payment=points * player.session.config['real_world_currency_per_point']
            + player.session.config['participation_fee'],
        )


page_sequence = [
    Instructions,
    FirmFormation,
    FormationWait,
    EffortDecision,
    ResultsWait,
    ResultsPeriod,
    FinalResults,
]
