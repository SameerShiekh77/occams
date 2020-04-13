import sqlalchemy as sa
from pyramid.httpexceptions import HTTPOk, HTTPBadRequest
from pyramid.csrf import check_csrf_token
from pyramid.view import view_config
import wtforms

from .. import _, models
from ..utils.forms import wtferrors, Form


@view_config(
    route_name='studies.reference_types',
    permission='view',
    renderer='json')
def list_json(context, request):
    dbsession = request.dbsession
    query = (
        dbsession.query(models.ReferenceType)
        .order_by(models.ReferenceType.title))
    return {
        'reference_types': [view_json(r, request) for r in query]
    }


@view_config(
    route_name='studies.reference_type',
    permission='view',
    renderer='json')
def view_json(context, request):
    return {
        '__url__': request.route_path(
            'studies.reference_type', reference_type=context.name),
        'id': context.id,
        'name': context.name,
        'title': context.title,
        'description': context.description,
        'reference_pattern': context.reference_pattern,
        'reference_hint': context.reference_hint
    }


@view_config(
    route_name='studies.reference_types',
    request_method='POST',
    permission='add',
    renderer='json')
@view_config(
    route_name='studies.reference_type',
    request_method='PUT',
    permission='edit',
    renderer='json')
def edit_json(context, request):
    check_csrf_token(request)

    dbsession = request.dbsession

    is_new = isinstance(context, models.ReferenceTypeFactory)

    def check_unique(form, field):
        query = (
            dbsession.query(models.ReferenceType)
            .filter_by(name=field.data))
        if not is_new:
            query = query.filter(models.ReferenceType.id != context.id)
        exists = (
            dbsession.query(sa.literal(True)).filter(query.exists()).scalar())
        if exists:
            raise wtforms.ValidationError(request.localizer.translate(
                _(u'Already exists')))

    class ReferenceTypeForm(Form):
        name = wtforms.StringField(
            validators=[
                wtforms.validators.InputRequired(),
                check_unique])
        title = wtforms.StringField(
            validators=[
                wtforms.validators.InputRequired()])
        description = wtforms.TextAreaField(
            validators=[
                wtforms.validators.Optional()])
        reference_pattern = wtforms.StringField(
            validators=[
                wtforms.validators.Optional()])
        reference_hint = wtforms.StringField(
            validators=[
                wtforms.validators.Optional()])

    form = ReferenceTypeForm.from_json(request.json_body)

    if not form.validate():
        raise HTTPBadRequest(json={'errors': wtferrors(form)})

    if is_new:
        reference_type = models.ReferenceType()
        dbsession.add(reference_type)
    else:
        reference_type = context

    form.populate_obj(reference_type)

    dbsession.flush()

    return view_json(reference_type, request)


@view_config(
    route_name='studies.reference_type',
    request_method='DELETE',
    permission='delete',
    renderer='json')
def delete_json(context, request):
    check_csrf_token(request)
    dbsession = request.dbsession
    exists = (
        dbsession.query(sa.literal(True))
        .filter(
            dbsession.query(models.PatientReference)
            .filter_by(reference_type=context)
            .exists())
        .scalar())
    if exists:
        raise HTTPBadRequest(
            body=_(u'This reference number still has data associated with it'))
    dbsession.delete(context)
    dbsession.flush()
    return HTTPOk()


@view_config(
    route_name='studies.reference_types',
    permission='view',
    xhr=True,
    request_param='vocabulary=available_reference_types',
    renderer='json')
def available_reference_types(context, request):
    dbsession = request.dbsession
    term = (request.GET.get('term') or '').strip()

    query = dbsession.query(models.ReferenceType)

    if term:
        query = query.filter(
            models.ReferenceType.title.ilike(u'%' + term + u'%'))

    query = query.order_by(models.ReferenceType.title.asc()).limit(100)

    return {
        '__query__': {'term': term},
        'reference_types': [view_json(reference_type, request)
                            for reference_type in query]
    }
