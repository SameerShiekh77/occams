from pyramid.httpexceptions import HTTPBadRequest, HTTPOk
from pyramid.csrf import check_csrf_token
from pyramid.view import view_config
import wtforms

from .. import _, models
from ..utils.forms import wtferrors, Form


@view_config(
    route_name='studies.sites',
    permission='view',
    xhr=True,
    renderer='json')
def list_json(context, request):
    dbsession = request.dbsession

    sites_query = (
        dbsession.query(models.Site)
        .order_by(models.Site.title.asc()))

    return {
        'sites': [view_json(site, request)
                  for site in sites_query
                  if request.has_permission('view', site)]
        }


@view_config(
    route_name='studies.site',
    xhr=True,
    permission='view',
    renderer='json')
def view_json(context, request):
    return {
        '__url__': request.route_path('studies.site', site=context.name),
        'id': context.id,
        'name': context.name,
        'title': context.title
    }


@view_config(
    route_name='studies.sites',
    permission='view',
    xhr=True,
    request_param='vocabulary=available_sites',
    renderer='json')
def available_sites(context, request):
    dbsession = request.dbsession
    term = (request.GET.get('term') or '').strip()

    query = dbsession.query(models.Site)

    if term:
        query = query.filter(models.Site.title.ilike('%' + term + '%'))

    query = query.order_by(models.Site.title.asc()).limit(100)

    return {
        '__query__': {'term': term},
        'sites': [view_json(site, request)
                  for site in query
                  if request.has_permission('view', site)]
    }


@view_config(
    route_name='studies.sites',
    permission='add',
    request_method='POST',
    xhr=True,
    renderer='json')
@view_config(
    route_name='studies.site',
    permission='edit',
    request_method='PUT',
    xhr=True,
    renderer='json')
def edit_json(context, request):
    dbsession = request.dbsession
    check_csrf_token(request)

    form = SiteSchema(context, request).from_json(request.json_body)

    if not form.validate():
        raise HTTPBadRequest(json=wtferrors(form))

    if isinstance(context, models.Site):
        site = context
    else:
        site = models.Site()
        dbsession.add(site)

    site.name = form.name.data
    site.title = form.title.data
    dbsession.flush()

    return view_json(site, request)


@view_config(
    route_name='studies.site',
    permission='delete',
    request_method='DELETE',
    xhr=True,
    renderer='json')
def delete_json(context, request):
    check_csrf_token(request)
    dbsession = request.dbsession
    dbsession.delete(context)
    dbsession.flush()
    msg = _(u'Successfully deleted: ${site}', mapping={'site': context.title})
    request.session.flash(msg)
    return HTTPOk(body=msg)


def SiteSchema(context, request):
    dbsession = request.dbsession

    def unique_name(form, field):
        query = dbsession.query(models.Site).filter_by(name=field.data)
        if isinstance(context, models.Site):
            query = query.filter(models.Site.id != context.id)
        (exists,) = dbsession.query(query.exists()).one()
        if exists:
            raise wtforms.ValidationError(request.localizer.translate(
                _(u'Site name already exists')))

    class SiteForm(Form):
        name = wtforms.StringField(
            validators=[
                wtforms.validators.InputRequired(),
                unique_name])
        title = wtforms.StringField(
            validators=[wtforms.validators.InputRequired()])

    return SiteForm
