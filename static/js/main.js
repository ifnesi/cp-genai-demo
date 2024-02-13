$(document).ready(function () {
    new DataTable('#data', {
        paging: true,
        lengthMenu: [
            [10, 25, 50, -1],
            [10, 25, 50, 'All']
        ],
        columnDefs: [
            { "targets": [0], "searchable": false, "orderable": false, "visible": true }
        ],
        order: [[1, 'asc']]
    });
});

function updateModalDelete(user_id) {
    $("#del_user_id").html(user_id);
}

function deleteLead() {
    url = "/del-lead/" + $("#del_user_id").html();
    $(location).attr("href", url);
}

function updateModalNew(user_id, company, first_name, last_name, email, phone_number) {
    $("#user_id").val(user_id);
    $("#company").val(company);
    $("#first_name").val(first_name);
    $("#last_name").val(last_name);
    $("#email").val(email);
    $("#phone_number").val(phone_number);
    $("#save_button").text("Update");
    $("#newLeadModalLabel").html("Update Lead");
    $("#div_user_id").show();
    $("#div_user_id").removeAttr("display");
}

function setModelNew() {
    $("#div_user_id").css("display", "none");
    $("#user_id").val("");
    $("#company").val("");
    $("#first_name").val("");
    $("#last_name").val("");
    $("#email").val("");
    $("#phone_number").val("");
    $("#save_button").text("Save");
    $("#newLeadModalLabel").html("Add New Lead");
}
