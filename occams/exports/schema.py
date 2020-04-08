"""
Generate form exports with contextual information.

Also incorporates:
    avrcdataexport/sql/UsableRandomization594.sql
    avrcdataexport/sql/UsableRandomization595.sql
    avrcdataexport/sql/UsableRandomization599.sql

"""

from datetime import datetime
from sqlalchemy import orm, null, cast, String, literal_column


from .. import models
from .plan import ExportPlan
from .codebook import types, row
from ..reporting import build_report
from ..utils.sql import group_concat, to_date


class SchemaPlan(ExportPlan):

    is_system = False

    @classmethod
    def from_sql(cls, dbsession, record):
        """
        Creates a plan instance from an internal query inspection
        """
        report = cls(dbsession)
        report.name = record.name
        report.title = record.title
        report.has_private = record.has_private
        report.has_rand = record.has_rand
        report.versions = sorted([datetime.strptime(v, '%Y-%m-%d').date()
                                  for v in record.versions.split(';')])
        return report

    @classmethod
    def from_schema(cls, dbsession, name):
        """
        Creates a plan from a schema name
        """
        subquery = _list_schemata_info(dbsession).subquery()
        query = dbsession.query(subquery).filter(subquery.c.name == name)
        return cls.from_sql(dbsession, query.one())

    @classmethod
    def list_all(cls, dbsession, include_rand=True, include_private=True):
        """
        Lists all the schema plans
        """
        subquery = _list_schemata_info(dbsession).subquery()
        query = dbsession.query(subquery)

        if not include_rand:
            query = query.filter(~subquery.c.has_rand)

        if not include_private:
            query = query.filter(~subquery.c.has_private)

        query = query.order_by(subquery.c.title)

        return [cls.from_sql(dbsession, r) for r in query]

    @property
    def _is_aeh_partner_form(self):
        return (
            'aeh' in self.dbsession.bind.url.database
            and self.name in (
                'IPartnerBio',
                'IPartnerContact',
                'IPartnerDemographics',
                'IPartnerDisclosure'))

    def codebook(self):
        session = self.dbsession
        knowns = [
            row('id', self.name, types.NUMBER, decimal_places=0,
                is_required=True, is_system=True),
            row('pid', self.name, types.STRING,
                is_required=True, is_system=True),
            row('site', self.name, types.STRING,
                is_required=True, is_system=True),
            row('enrollment', self.name, types.NUMBER, decimal_places=0,
                is_collection=True, is_system=True),
            row('enrollment_ids', self.name, types.NUMBER, decimal_places=0,
                is_collection=True, is_system=True)]

        if self._is_aeh_partner_form:
            knowns.extend([
                row('partner_id', self.name, types.NUMBER, decimal_places=0,
                    is_required=True, is_system=True,
                    desc=u'The partner linkage ID this form was collected for.'),
                row('parter_pid', self.name, types.STRING, is_system=True,
                    desc=u'The partner linkage PID this form was collected for. '
                         u'Available only if the partner is actually enrolled.')])

        if self.has_rand:
            knowns.extend([
                row('block_number', self.name, types.NUMBER, decimal_places=0,
                    is_required=True, is_system=True),
                row('randid', self.name, types.STRING, is_required=True,
                    is_system=True),
                row('arm_name', self.name, types.STRING, is_required=True,
                    is_system=True)])

        knowns.extend([
            row('visit_cycles', self.name, types.STRING, is_collection=True,
                is_system=True),
            row('visit_date', self.name, types.DATE, is_system=True),
            row('visit_id', self.name, types.NUMBER, decimal_places=0, is_system=True),
            row('form_name', self.name, types.STRING,
                is_required=True, is_system=True),
            row('form_publish_date', self.name, types.STRING,
                is_required=True, is_system=True),
            row('state', self.name, types.STRING,
                is_required=True, is_system=True),
            row('collect_date', self.name, types.DATE,
                is_required=True, is_system=True),
            row('not_done', self.name, types.BOOLEAN,
                is_required=True, is_system=True)])

        for column in knowns:
            yield column

        query = (
            session.query(models.Attribute)
            .join(models.Schema)
            .filter(models.Schema.name == self.name)
            .filter(models.Schema.publish_date.in_(self.versions))
            .filter(models.Schema.retract_date == null()))

        query = (
            query.order_by(
                models.Attribute.name,
                models.Schema.publish_date))

        for attribute in query:
            yield row(attribute.name, attribute.schema.name, attribute.type,
                      decimal_places=attribute.decimal_places,
                      form=attribute.schema.title,
                      publish_date=attribute.schema.publish_date,
                      title=attribute.title,
                      desc=attribute.description,
                      is_required=attribute.is_required,
                      is_collection=attribute.is_collection,
                      order=attribute.order,
                      is_private=attribute.is_private,
                      choices=[(c.name, c.title)
                               for c in attribute.choices.values()])

        footer = [
            row('create_date', self.name, types.DATE,
                is_required=True, is_system=True),
            row('create_user', self.name, types.STRING,
                is_required=True, is_system=True),
            row('modify_date', self.name, types.DATE,
                is_required=True, is_system=True),
            row('modify_user', self.name, types.STRING, is_required=True,
                is_system=True)]

        for column in footer:
            yield column

    def data(self,
             use_choice_labels=False,
             expand_collections=False,
             ignore_private=True):
        session = self.dbsession
        ids_query = (
            session.query(models.Schema.id)
            .filter(models.Schema.publish_date.in_(self.versions)))
        ids = [id for id, in ids_query]

        report = build_report(
            session,
            self.name,
            ids=ids,
            expand_collections=expand_collections,
            use_choice_labels=use_choice_labels,
            ignore_private=ignore_private)

        query = (
            session.query(report.c.id.label('id'))
            .add_columns(
                session.query(models.Patient.pid)
                .join(models.Context,
                      (models.Context.external == u'patient')
                      & (models.Context.key == models.Patient.id))
                .filter(models.Context.entity_id == report.c.id)
                .correlate(report)
                .as_scalar()
                .label('pid'))
            .add_columns(
                session.query(models.Site.name)
                .select_from(models.Patient)
                .join(models.Site)
                .join(models.Context,
                      (models.Context.external == u'patient')
                      & (models.Context.key == models.Patient.id))
                .filter(models.Context.entity_id == report.c.id)
                .correlate(report)
                .as_scalar()
                .label('site'))
            .add_columns(
                session.query(group_concat(models.Study.name, ';'))
                .select_from(models.Enrollment)
                .join(models.Study)
                .join(models.Context,
                      (models.Context.external == u'enrollment')
                      & (models.Context.key == models.Enrollment.id))
                .filter(models.Context.entity_id == report.c.id)
                .group_by(models.Context.entity_id)
                .correlate(report)
                .as_scalar()
                .label('enrollment'))
            .add_columns(
                session.query(group_concat(models.Enrollment.id, ';'))
                .select_from(models.Enrollment)
                .join(models.Context,
                      (models.Context.external == u'enrollment')
                      & (models.Context.key == models.Enrollment.id))
                .filter(models.Context.entity_id == report.c.id)
                .group_by(models.Context.entity_id)
                .correlate(report)
                .as_scalar()
                .label('enrollment_ids'))
            )

        if self._is_aeh_partner_form:
            PartnerPatient = orm.aliased(models.Patient)
            query = (
                query
                .add_columns(
                    session.query(models.Partner.id)
                    .select_from(models.Partner)
                    .join(models.Context,
                          (models.Context.external == u'partner')
                          & (models.Context.key == models.Partner.id))
                    .filter(models.Context.entity_id == report.c.id)
                    .correlate(report)
                    .as_scalar()
                    .label('partner_id'))
                .add_columns(
                    session.query(PartnerPatient.pid)
                    .select_from(models.Partner)
                    .join(PartnerPatient, models.Partner.enrolled_patient)
                    .join(models.Context,
                          (models.Context.external == u'partner')
                          & (models.Context.key == models.Partner.id))
                    .filter(models.Context.entity_id == report.c.id)
                    .correlate(report)
                    .as_scalar()
                    .label('partner_pid')))

        if self.has_rand:
            query = (
                query
                .add_columns(
                    session.query(models.Stratum.block_number)
                    .select_from(models.Stratum)
                    .join(models.Context,
                          (models.Context.external == u'stratum')
                          & (models.Context.key == models.Stratum.id))
                    .filter(models.Context.entity_id == report.c.id)
                    .correlate(report)
                    .as_scalar()
                    .label('block_number'))
                .add_columns(
                    session.query(models.Stratum.randid)
                    .select_from(models.Stratum)
                    .join(models.Context,
                          (models.Context.external == u'stratum')
                          & (models.Context.key == models.Stratum.id))
                    .filter(models.Context.entity_id == report.c.id)
                    .correlate(report)
                    .as_scalar()
                    .label('randid'))
                .add_columns(
                    session.query(models.Arm.title)
                    .select_from(models.Stratum)
                    .join(models.Context,
                          (models.Context.external == u'stratum')
                          & (models.Context.key == models.Stratum.id))
                    .filter(models.Context.entity_id == report.c.id)
                    .join(models.Stratum.arm)
                    .correlate(report)
                    .as_scalar()
                    .label('arm_name')))

        query = (
            query
            .add_columns(
                session.query(group_concat(models.Study.title
                                           + literal_column(u"'('")
                                           + cast(models.Cycle.week, String)
                                           + literal_column(u"')'"),
                                           literal_column(u"';'")))
                .select_from(models.Visit)
                .join(models.Visit.cycles)
                .join(models.Cycle.study)
                .join(models.Context,
                      (models.Context.external == u'visit')
                      & (models.Context.key == models.Visit.id))
                .filter(models.Context.entity_id == report.c.id)
                .group_by(models.Context.entity_id)
                .correlate(report)
                .as_scalar()
                .label('visit_cycles'))
            .add_columns(
                session.query(models.Visit.id)
                .select_from(models.Visit)
                .join(models.Context,
                      (models.Context.external == u'visit')
                      & (models.Context.key == models.Visit.id))
                .filter(models.Context.entity_id == report.c.id)
                .correlate(report)
                .as_scalar()
                .label('visit_id'))
            .add_columns(
                session.query(models.Visit.visit_date)
                .select_from(models.Visit)
                .join(models.Context,
                      (models.Context.external == u'visit')
                      & (models.Context.key == models.Visit.id))
                .filter(models.Context.entity_id == report.c.id)
                .correlate(report)
                .as_scalar()
                .label('visit_date'))
        )

        query = query.add_columns(
            *[c for c in report.columns if c.name != 'id'])

        return query


def _list_schemata_info(dbsession):
    InnerSchema = orm.aliased(models.Schema)
    OuterSchema = orm.aliased(models.Schema)

    schemata_query = (
        dbsession.query(OuterSchema.name.label('name'))
        .add_columns(literal_column("'schema'").label('type'))
        .add_columns(
            dbsession.query(models.Attribute)
            .filter(models.Attribute.is_private)
            .join(InnerSchema)
            .filter(InnerSchema.name == OuterSchema.name)
            .correlate(OuterSchema)
            .exists()
            .label('has_private'))
        .add_columns(
            dbsession.query(models.Entity)
            .join(models.Entity.contexts)
            .filter(models.Context.external == 'stratum')
            .join(models.Stratum, models.Context.key == models.Stratum.id)
            .join(InnerSchema, models.Entity.schema)
            .filter(InnerSchema.name == OuterSchema.name)
            .correlate(OuterSchema)
            .exists()
            .label('has_rand'))
        .add_columns(
            dbsession.query(InnerSchema.title)
            .select_from(InnerSchema)
            .filter(InnerSchema.name == OuterSchema.name)
            .filter(InnerSchema.publish_date != null())
            .filter(InnerSchema.retract_date == null())
            .order_by(InnerSchema.publish_date.desc())
            .limit(1)
            .correlate(OuterSchema)
            .as_scalar()
            .label('title'))
        .add_columns(
            dbsession.query(
                group_concat(to_date(InnerSchema.publish_date), ';'))
            .filter(InnerSchema.name == OuterSchema.name)
            .filter(InnerSchema.publish_date != null())
            .filter(InnerSchema.retract_date == null())
            .group_by(InnerSchema.name)
            .correlate(OuterSchema)
            .as_scalar()
            .label('versions'))
        .filter(OuterSchema.publish_date != null())
        .filter(OuterSchema.retract_date == null()))

    schemata_query = (
        schemata_query
        .group_by(OuterSchema.name)
        .from_self())

    return schemata_query
