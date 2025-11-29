
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
class Subsession(BaseSubsession):
    formation_type = models.StringField()
    returns_type = models.StringField()
class Group(BaseGroup):
    period_index = models.IntegerField()
class Player(BasePlayer):
    effort_to_firm = models.IntegerField()
    effort_to_self = models.IntegerField()
    firm_id = models.IntegerField()
    is_firm_owner = models.IntegerField()
    firm_size = models.IntegerField()
    firm_total_effort = models.FloatField()
    firm_per_capita_effort = models.FloatField()
    firm_per_capita_payoff = models.FloatField()
    autarkic = models.IntegerField()
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
    
def mpcr_linear(n):
    
    # Table 2 MPCRs by firm size
    mpcr_by_n = {
        2: 0.65,
        3: 0.55,
        4: 0.49,
        5: 0.45,
        6: 0.42,
    }
    return mpcr_by_n[n]
    
def production_increasing(E):
    
    # f(E) = a * E^b with calibration from design
    # a ≈ 0.2496, b ≈ 1.5952
    if E <= 0:
        return 0.0
    a = 0.2496
    b = 1.5952
    return a * (E ** b)
    
def set_firms_exogenous(subsession: Subsession):
    
    # For now, simple placeholder: everyone in one firm per round.
    players = subsession.get_players()
    for p in players:
        p.firm_id = 1
        p.is_firm_owner = 1 if p.id_in_subsession == 1 else 0
    
def set_payoffs(subsession: Subsession):
    
    session = subsession.session
    formation_type = subsession.formation_type
    returns_type = subsession.returns_type
    
    players = subsession.get_players()
    
    # group players by firm_id (autarkic players will have firm_id=None or 0)
    firms = {}
    for p in players:
        fid = p.firm_id
        if not fid:
            continue
        firms.setdefault(fid, []).append(p)
    
    # handle autarky: players with no firm_id get 8 points from self-effort
    for p in players:
        if not p.firm_id:
            p.autarkic = 1
            if p.effort_to_self is None:
                p.effort_to_self = C.EFFORT_ENDOWMENT
            p.payoff = p.effort_to_self
    
    for fid, members in firms.items():
        n = len(members)
        total_effort = sum(m.effort_to_firm or 0 for m in members)
    
        if returns_type == 'constant':
            alpha = mpcr_linear(n)
            total_output = alpha * n * total_effort
        else:
            total_output = production_increasing(total_effort)
    
        if n > 0:
            per_capita_output = total_output / n
        else:
            per_capita_output = 0
    
        for m in members:
            m.autarkic = 0
            m.firm_size = n
            m.firm_total_effort = total_effort
            m.firm_per_capita_effort = total_effort / n if n > 0 else 0
            m.firm_per_capita_payoff = per_capita_output
            if m.effort_to_self is None:
                m.effort_to_self = C.EFFORT_ENDOWMENT - (m.effort_to_firm or 0)
            m.payoff = m.effort_to_self + per_capita_output
    
class Instructions(Page):
    form_model = 'player'
    @staticmethod
    def is_displayed(player: Player):
        
        return player.round_number == 1
        
class FirmFormation(Page):
    form_model = 'player'
    timeout_seconds = 120
    @staticmethod
    def is_displayed(player: Player):
        session = player.session
        subsession = player.subsession
        
        # Skip firm formation in exogenous treatments
        return player.subsession.formation_type == 'endogenous'
        
class EffortDecision(Page):
    form_model = 'player'
    form_fields = ['effort_to_firm']
    timeout_seconds = 60
    @staticmethod
    def vars_for_template(player: Player):
        
        return dict(
            endowment=C.EFFORT_ENDOWMENT,
        )
        
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        session = player.session
        subsession = player.subsession
        
        # enforce effort bounds and compute effort_to_self
        if player.effort_to_firm is None:
            player.effort_to_firm = 0
        if player.effort_to_firm < 0 or player.effort_to_firm > C.EFFORT_ENDOWMENT:
            # let oTree raise an error if this happens
            raise ValueError('effort_to_firm out of bounds')
        player.effort_to_self = C.EFFORT_ENDOWMENT - player.effort_to_firm
        
        # after all players decide in this round, compute payoffs
        if player.id_in_subsession == 1:
            set_payoffs(player.subsession)
        
class ResultsPeriod(Page):
    form_model = 'player'
    timeout_seconds = 30
    @staticmethod
    def vars_for_template(player: Player):
        session = player.session
        subsession = player.subsession
        
        # show summary of all firms this period
        subsession = player.subsession
        players = subsession.get_players()
        
        firms = {}
        for p in players:
            fid = p.firm_id
            if not fid:
                continue
            d = firms.setdefault(fid, dict(size=None, total_effort=0, per_capita_effort=0, per_capita_payoff=0))
            d['total_effort'] += p.effort_to_firm or 0
        
        for fid, d in firms.items():
            members = [p for p in players if p.firm_id == fid]
            n = len(members)
            d['size'] = n
            d['per_capita_effort'] = d['total_effort'] / n if n > 0 else 0
            # assume all members have same per_capita_payoff
            if n > 0:
                d['per_capita_payoff'] = members[0].firm_per_capita_payoff or 0
        
        firm_list = [dict(firm_id=fid, **d) for fid, d in sorted(firms.items())]
        
        return dict(
            firm_list=firm_list,
        )
        
class FinalResults(Page):
    form_model = 'player'
    @staticmethod
    def is_displayed(player: Player):
        
        return player.round_number == C.NUM_ROUNDS
        
    @staticmethod
    def vars_for_template(player: Player):
        session = player.session
        
        # total points over all rounds
        all_players = player.in_all_rounds()
        points = sum(p.payoff for p in all_players)
        
        return dict(
            total_points=points,
            total_payment=points * player.session.config['real_world_currency_per_point'] + player.session.config['participation_fee'],
        )
        
page_sequence = [Instructions, FirmFormation, EffortDecision, ResultsPeriod, FinalResults]