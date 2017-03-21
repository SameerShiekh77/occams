from copy import deepcopy
from datetime import date
import json
import shutil
import tempfile

import six
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import FileIter
from pyramid.session import check_csrf_token
from pyramid.view import view_config
import wtforms
import wtforms.widgets.html5
import wtforms.ext.dateutil.fields
from wtforms_components import DateRange

from .. import _, models
from ..utils.forms import Form
from ..renderers import make_form, render_form, apply_data
from . import field as field_views


@view_config(
    route_name='forms.version',
    permission='view',
    renderer='../templates/version/view.pt')
def view(context, request):
    return {}


@view_config(
    route_name='forms.version',
    xhr=True,
    permission='view',
    renderer='json')
def view_json(context, request):
    """
    Edits form version metadata (not the fields)
    """
    return {
        '__url__': request.route_path(
            'forms.version',
            form=context.name,
            version=str(context.publish_date or context.id)),
        '__types__': field_views.types,
        'id': context.id,
        'name': context.name,
        'title': context.title,
        'description': context.description,
        'publish_date': context.publish_date and str(context.publish_date),
        'retract_date': context.retract_date and str(context.retract_date),
        'fields': field_views.list_json(context['fields'], request)['fields'],
        }


@view_config(
    route_name='forms.version',
    permission='view',
    request_param='download=json')
def download_json(context, request):
    fp = six.moves.cStringIO()
    json.dump(context.to_json(deep=True), fp, indent=2)
    fp.seek(0)
    response = request.response
    response.content_type = 'application/json'
    response.content_disposition = 'attachment; filename="%s-%s.json"' % (
        context.name,
        context.publish_date.isoformat() if context.publish_date else 'draft')
    response.app_iter = FileIter(fp)
    return response


@view_config(
    route_name='forms.version_preview',
    permission='view',
    renderer='../templates/version/preview.pt')
def preview(context, request):
    """
    Preview form for test-drivining.
    """
    dbsession = request.dbsession
    form_class = make_form(dbsession, context, show_metadata=False)
    form = form_class(request.POST)
    form_id = 'form-preview'
    entity = None
    attachments = {}

    if request.method == 'POST' and form.validate():
        upload_path = tempfile.mkdtemp()
        entity = models.Entity(schema=context)
        try:
            apply_data(dbsession, entity, form.data, upload_path)
        finally:
            shutil.rmtree(upload_path)

        attachments = {a.id: a for a in six.itervalues(entity.attachments)}

        # Remove from session so entity or attributes don't persist in db
        dbsession.expunge(entity)

    return {
        'entity': entity,
        'attachments': attachments,
        'form_id': form_id,
        'form_content': render_form(
            form,
            cancel_url=request.current_route_path(),
            attr={
                'id': form_id,
                'method': 'POST',
                'action': request.current_route_path(_query={}),
                'role': 'form'
                })
        }


@view_config(
    route_name='forms.version',
    xhr=True,
    permission='edit',
    request_method='PUT',
    request_param='publish',
    renderer='json')
def publish_json(context, request):
    check_csrf_token(request)
    dbsession = request.dbsession

    def check_unique_publish_date(form, field):
        (exists,) = (
            dbsession.query(
                dbsession.query(models.Schema)
                .filter_by(name=context.name, publish_date=field.data)
                .filter(models.Schema.id != context.id)
                .exists())
            .one())
        if exists:
            raise wtforms.ValidationError(_(
                'Version ${publish_date} is already in use',
                mapping={'publish_date': field.data}))

    def check_valid_timeline(form, field):
        publish_date = form.publish_date.data
        retract_date = form.retract_date.data
        if not publish_date:
            raise wtforms.ValidationError(_(
                u'Cannot retract an un-published form'))
        if retract_date < publish_date:
            raise wtforms.ValidationError(_('Must be after publish date'))

    # TODO: should move this out, but need to ensure context is removed
    # from helper validators
    class PublishForm(Form):
        publish_date = wtforms.ext.dateutil.fields.DateField(
            validators=[
                wtforms.validators.Optional(),
                DateRange(min=date(1900, 1, 1)),
                check_unique_publish_date
            ],
            widget=wtforms.widgets.html5.DateInput())
        retract_date = wtforms.ext.dateutil.fields.DateField(
            validators=[
                wtforms.validators.Optional(),
                DateRange(min=date(1900, 1, 1)),
                check_valid_timeline
            ],
            widget=wtforms.widgets.html5.DateInput())

    form = PublishForm.from_json(request.json_body)

    if not form.validate():
        return HTTPBadRequest(json={'errors': form.errors})

    context.publish_date = form.publish_date.data
    context.retract_date = form.retract_date.data

    dbsession.flush()

    return view_json(context, request)


class SchemaForm(Form):

    title = wtforms.StringField(
        validators=[
            wtforms.validators.InputRequired(),
            wtforms.validators.Length(min=3, max=128)])

    description = wtforms.StringField(
        validators=[wtforms.validators.Optional()])


@view_config(
    route_name='forms.version',
    xhr=True,
    permission='edit',
    request_method='PUT',
    renderer='json')
def edit_json(context, request):
    check_csrf_token(request)

    dbsession = request.dbsession
    form = SchemaForm.from_json(request.json_body)

    if not form.validate():
        return HTTPBadRequest(json={'errors': form.errors})

    context.title = form.title.data
    context.description = form.description.data
    dbsession.flush()

    request.session.flash(_(u'Changes saved'), 'success')

    return view_json(context, request)


@view_config(
    route_name='forms.version_editor',
    permission='edit',
    renderer='../templates/version/editor.pt')
def editor(context, request):
    return {}


@view_config(
    route_name='forms.version',
    permission='draft',
    request_method='POST',
    request_param='draft',
    xhr=True,
    renderer='json')
def draft_json(context, request):
    """
    Drafts a new version of a published form.
    """
    check_csrf_token(request)
    dbsession = request.dbsession
    schema = context
    if not schema.publish_date:
        raise HTTPBadRequest(json={
            'user_message': _(u'Cannot draft new from unpublished version')})
    draft = deepcopy(schema)
    dbsession.add(draft)
    dbsession.flush()
    request.session.flash(_(u'Successfully drafted new version'))
    return {
        # Hint the next resource to look for data
        '__next__': request.route_path('forms.version',
                                       form=draft.name,
                                       version=draft.id)
        }


@view_config(
    route_name='forms.version',
    permission='delete',
    request_method='DELETE',
    xhr=True,
    renderer='json')
def delete_json(context, request):
    """
    Edits form version metadata (not the fields)
    """
    check_csrf_token(request)
    dbsession = request.dbsession

    dbsession.delete(context)

    if context.publish_date:
        msg = _(u'Successfully deleted ${name} version ${version}',
                mapping={'name': context.name,
                         'version': context.publish_date})
    else:
        msg = _(u'Successfully deleted draft of ${name}',
                mapping={'name': context.name})

    request.session.flash(msg)

    return {
        # Hint the next resource to look for data
        '__next__': request.current_route_path(_route_name='forms.index')
        }
