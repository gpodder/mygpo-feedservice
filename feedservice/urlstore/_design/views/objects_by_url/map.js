function(doc)
{
    if(doc.doc_type == 'URLObject')
    {
        emit(doc.url, null);
    }
}
